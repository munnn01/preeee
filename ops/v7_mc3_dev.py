#!/usr/bin/env python
"""Frozen V7 H.265 mc3 diagnostic on the already used 200-source DEV split."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import time

import numpy as np

from ops.codec_search_ar import QPS
from ops.dual_codec_search import digest, write_json
from ops.paper_heldout_mc3 import compare as compare_curves, timed_inference
from ops.v5_dev_agreement import load_locked_dev_cache
from ops.v6_dev_residual import predicted_measurements, select_residual
from ops.v6_frozen import load_frozen_v6
from ops.v7_dev_transfer import choose_v7, load_cache_stage, load_proxy_stage
from ops.v7_pixel_proxy import (PLAN_SHA256, REPO, find_planned_videos,
                                sha256, verify_protocol)
from src.codecs.standard import StandardCodec, ffmpeg_available
from src.data.video_dataset import VideoClipDataset
from src.models.codec_search import CANDIDATES, make_candidates, normalized_bpp
from src.tasks.action_recognition import (ActionRecognitionAnalyzer, _canon,
                                          kinetics_categories,
                                          kinetics_category_index)

EXPERIMENT = "v7_h265_mc3_reused_dev_diagnostic"
PREREG_COMMIT = "53a1ad44c9c659829d97046e117e9d50928dada1"
V7_RESULT_COMMIT = "c9902af498281a1f85c3fc9fea8e19d56424ff86"
V7_RESULT_SHA256 = "7026c427f92574508db966d61e082018e0c18a66c50592d24d9c2fe9046c742c"
V7_CODE_COMMIT = "2c0a29836101fced7a91b7ff136a8b929b6d7c2b"
DEV_PIXEL_SHA256 = "f20263168c67dd5f275bad9ebc3ff3ef212b9f300e601bc4dd88dde05720a17f"
SELECTION = REPO / "configs/v7_mc3_dev_selection.json"
RESULT = REPO / "results/v7_dev_transfer/h265_result.json"
PREREG = REPO / "docs/PREREGISTRATION_V7_MC3_DEV.md"
SHARDS = 4
SEED = 20261004
DRAWS = 2000
ARMS = ("identity", "v6", "v7")
COMPARISONS = (("V6_vs_identity", "identity", "v6"),
               ("V7_vs_identity", "identity", "v7"),
               ("V7_vs_V6", "v6", "v7"))


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", *args], cwd=REPO)


def preregistered_head() -> str:
    subprocess.run(["git", "-c", f"safe.directory={REPO.as_posix()}",
                    "merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD"],
                   cwd=REPO, check=True, capture_output=True)
    if PREREG.read_bytes().replace(b"\r\n", b"\n") != git(
            "show", f"{PREREG_COMMIT}:docs/PREREGISTRATION_V7_MC3_DEV.md"):
        raise ValueError("V7 mc3 protocol differs from preregistration commit")
    if sha256(RESULT) != V7_RESULT_SHA256 or git(
            "show", f"{V7_RESULT_COMMIT}:results/v7_dev_transfer/h265_result.json"
    ) != RESULT.read_bytes():
        raise ValueError("frozen V7 DEV result changed")
    return git("rev-parse", "HEAD").decode().strip()


def frozen_selection(path: Path = SELECTION) -> tuple[dict, str]:
    preregistered_head()
    relative = path.resolve().relative_to(REPO.resolve()).as_posix()
    if path.read_bytes() != git("show", f"HEAD:{relative}"):
        raise ValueError("selection manifest differs from pinned Git commit")
    data = json.loads(path.read_text(encoding="utf-8"))
    plan, _ = verify_protocol()
    ids = plan["stage_ids"]["dev"]
    if (data.get("experiment") != EXPERIMENT or data.get("codec") != "h265"
            or data.get("qps") != list(QPS) or data.get("shards") != SHARDS
            or data.get("source_plan_sha256") != PLAN_SHA256
            or data.get("source_fingerprint") != plan["source_fingerprints"]["dev"]
            or data.get("v7_result_sha256") != V7_RESULT_SHA256
            or data.get("dev_pixel_records_sha256") != DEV_PIXEL_SHA256
            or data.get("v7_policy") != {"mode": "V7_pixel", "threshold": -0.02,
                                         "pixel_weight": 0.25}
            or len(data.get("sources", [])) != 200
            or [r["sequence_id"] for r in data["sources"]] != ids):
        raise ValueError("selection manifest differs from locked V7 DEV design")
    for row in data["sources"]:
        if (len(row["source_sha256"]) != 64 or len(row["measurements"]) != len(QPS)
                or [m["qp"] for m in row["measurements"]] != list(QPS)):
            raise ValueError("invalid frozen source/QP selection")
        for item in row["measurements"]:
            if item["identity"] != "identity128":
                raise ValueError("identity stream changed")
            if set(item["cached_bpp"]) != set(ARMS):
                raise ValueError("incomplete cached bpp")
            for arm in ARMS:
                if (item[arm] not in CANDIDATES
                        or not np.isfinite(item["cached_bpp"][arm])
                        or item["cached_bpp"][arm] <= 0):
                    raise ValueError("invalid candidate or cached bpp")
            for a in ARMS:
                for b in ARMS:
                    if (item[a] == item[b] and
                            item["cached_bpp"][a] != item["cached_bpp"][b]):
                        raise ValueError("shared stream has inconsistent bpp")
    return data, sha256(path)


def prepare_selection(cache_root: Path, pixel_root: Path, out: Path) -> dict:
    if out.exists():
        raise ValueError("selection output must be new")
    head = preregistered_head()
    plan, _ = verify_protocol()
    lock, lock_sha = load_locked_dev_cache()
    rows, risk, v2_policy = load_cache_stage(cache_root, "dev", plan, lock)
    pixels, pixel_hashes = load_proxy_stage(pixel_root, "dev", plan, V7_CODE_COMMIT)
    if pixel_hashes["records_sha256"] != DEV_PIXEL_SHA256:
        raise ValueError("V7 DEV pixel record bytes changed")
    v6_policy, models = load_frozen_v6()
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    policy = result["calibration"]["selected_policy"]
    if policy != {"mode": "V7_pixel", "threshold": -0.02, "pixel_weight": 0.25}:
        raise ValueError("V7 selected policy changed")
    prepared = predicted_measurements(rows, risk, v2_policy, models)
    sources, counts = [], {"V6": Counter(), "V7": Counter()}
    for key, row, video in zip(plan["stage_ids"]["dev"], rows, prepared, strict=True):
        if row["sequence_id"] != key:
            raise ValueError("V7 DEV cache order changed")
        pixel = pixels[key]
        measurements = []
        for measurement, obs, base, probabilities in video:
            v6 = select_residual(obs, base, probabilities, v6_policy)
            v7 = choose_v7(obs, v6, probabilities,
                           pixel["proxy_by_candidate"], policy)
            names = {"identity": "identity128", "v6": obs[v6]["name"],
                     "v7": obs[v7]["name"]}
            counts["V6"][names["v6"]] += 1
            counts["V7"][names["v7"]] += 1
            bpp = {arm: float(next(c["bpp"] for c in measurement["candidates"]
                                   if c["name"] == name))
                   for arm, name in names.items()}
            measurements.append({"qp": measurement["qp"], **names,
                                 "cached_bpp": bpp})
        sources.append({"sequence_id": key,
                        "source_sha256": pixel["source_sha256"],
                        "measurements": measurements})
    if {k: dict(v) for k, v in counts.items()} != result["dev"]["choices"]:
        raise ValueError("frozen V6/V7 choices differ from committed DEV result")
    selection = {"experiment": EXPERIMENT, "scope": "reused DEV; diagnostic only",
                 "codec": "h265", "qps": list(QPS), "shards": SHARDS,
                 "source_plan_sha256": PLAN_SHA256,
                 "source_fingerprint": plan["source_fingerprints"]["dev"],
                 "dev_pixel_records_sha256": DEV_PIXEL_SHA256,
                 "dev_pixel_manifest_sha256": pixel_hashes["manifest_sha256"],
                 "dev_cache_lock_sha256": lock_sha,
                 "v7_result_sha256": V7_RESULT_SHA256,
                 "v7_result_commit": V7_RESULT_COMMIT,
                 "preregistration_commit": PREREG_COMMIT,
                 "selection_generator_commit": head,
                 "v6_policy": v6_policy, "v7_policy": policy,
                 "choices": {k: dict(v) for k, v in counts.items()},
                 "sources": sources}
    write_json(out, selection)
    return {"sources": len(sources), "selection_sha256": sha256(out),
            "choices": selection["choices"]}


def decode_source(path: Path) -> np.ndarray:
    dataset = VideoClipDataset.__new__(VideoClipDataset)
    dataset.num_frames, dataset.frame_size = 16, 128
    dataset.temporal_stride, dataset.train = 2, False
    return dataset._read_clip(str(path))


def evaluate_source(source: dict, path: Path, analyzer, codec,
                    label: int) -> dict:
    if sha256(path) != source["source_sha256"]:
        raise ValueError(f"source video bytes changed: {source['sequence_id']}")
    import cv2
    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    if not ok:
        raise ValueError(f"undecodable DEV source: {source['sequence_id']}")
    variants = make_candidates(decode_source(path))
    measurements = []
    for expected in source["measurements"]:
        qp = expected["qp"]
        streams = {}
        for arm in ARMS:
            name = expected[arm]
            if name in streams:
                continue
            candidate = variants[name]
            _t, h, w, _c = candidate.shape
            start = time.perf_counter()
            reconstructed, native_bpp = codec._encode_decode_clip(candidate, qp=qp)
            encode_decode_s = time.perf_counter() - start
            actual_bpp = normalized_bpp(native_bpp, h, w)
            if abs(actual_bpp - expected["cached_bpp"][arm]) > 1e-9:
                raise ValueError(f"codec bpp differs from V2 cache: {source['sequence_id']} QP {qp} {name}")
            prediction, inference_s = timed_inference(analyzer, reconstructed)
            streams[name] = {"name": name, "bpp": actual_bpp,
                             "predicted_class_index": prediction,
                             "correct": bool(prediction == label),
                             "encode_decode_s": encode_decode_s,
                             "inference_s": inference_s}
        measurements.append({"qp": qp, "identity": streams[expected["identity"]],
                             "v6": streams[expected["v6"]],
                             "v7": streams[expected["v7"]],
                             "unique_streams": len(streams)})
    return {"sequence_id": source["sequence_id"],
            "source_sha256": source["source_sha256"], "label": label,
            "measurements": measurements}


def validate_record(record: dict, expected: dict, label: int) -> None:
    if (record.get("sequence_id") != expected["sequence_id"]
            or record.get("source_sha256") != expected["source_sha256"]
            or record.get("label") != label
            or len(record.get("measurements", [])) != len(QPS)):
        raise ValueError("stale/incomplete V7 mc3 record")
    for item, choice in zip(record["measurements"], expected["measurements"]):
        if item["qp"] != choice["qp"]:
            raise ValueError("V7 mc3 QP order changed")
        if item["unique_streams"] != len({choice[arm] for arm in ARMS}):
            raise ValueError("V7 mc3 stream reuse count changed")
        for arm in ARMS:
            value = item[arm]
            if (value["name"] != choice[arm]
                    or abs(value["bpp"] - choice["cached_bpp"][arm]) > 1e-9
                    or not isinstance(value["correct"], bool)
                    or not 0 <= value["predicted_class_index"] < 400
                    or value["correct"] != (value["predicted_class_index"] == label)):
                raise ValueError("V7 mc3 cached stream/score changed")


def run_shard(root: Path, shard: int, out_dir: Path) -> dict:
    if shard not in range(SHARDS) or not root.is_dir() or not ffmpeg_available():
        raise ValueError("invalid shard/source root or ffmpeg unavailable")
    head = preregistered_head()
    selection, selection_sha = frozen_selection()
    assigned = selection["sources"][shard::SHARDS]
    if len(assigned) != 50:
        raise ValueError("invalid V7 mc3 source partition")
    paths = find_planned_videos(root, [r["sequence_id"] for r in assigned])
    if kinetics_categories("mc3_18") != kinetics_categories("r3d_18"):
        raise ValueError("mc3 Kinetics category order changed")
    categories = kinetics_category_index("mc3_18")
    torch = __import__("torch")
    torchvision = __import__("torchvision")
    import cv2
    torch.manual_seed(53)
    torch.set_num_threads(2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    analyzer = ActionRecognitionAnalyzer("mc3_18", clip_size=112).freeze().to(device)
    codec = StandardCodec("h265", preset="medium", strict_decode=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for number, source in enumerate(assigned, 1):
        key = source["sequence_id"]
        label = categories.get(_canon(key.split("/")[0]))
        if label is None:
            raise ValueError(f"unmapped Kinetics category: {key}")
        checkpoint = out_dir / "cache" / f"clip_{number:03d}.json"
        if checkpoint.exists():
            record = json.loads(checkpoint.read_text(encoding="utf-8"))
        else:
            record = evaluate_source(source, paths[key], analyzer, codec, label)
            write_json(checkpoint, record)
        validate_record(record, source, label)
        records.append(record)
        print(f"[V7 mc3 DEV] shard={shard} {number}/50", flush=True)
    raw = out_dir / "shard_records.jsonl"
    raw.write_bytes("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
                            for row in records).encode("utf-8"))
    manifest = {"experiment": EXPERIMENT, "scope": "reused DEV; diagnostic only",
                "codec": "h265", "stage": "mc3", "shard": shard, "shards": SHARDS,
                "n": 50, "source_ids": [r["sequence_id"] for r in assigned],
                "shard_fingerprint": digest([r["sequence_id"] for r in assigned]),
                "source_fingerprint": selection["source_fingerprint"],
                "selection_sha256": selection_sha,
                "preregistration_commit": PREREG_COMMIT,
                "code_commit": head, "records_sha256": sha256(raw),
                "qps": list(QPS), "analyzer": "mc3_18",
                "bootstrap_unit": "source video; all QPs and arms paired",
                "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
                "versions": {"python": platform.python_version(),
                             "torch": torch.__version__,
                             "torchvision": torchvision.__version__,
                             "opencv": cv2.__version__,
                             "ffmpeg": subprocess.check_output(
                                 ["ffmpeg", "-version"], text=True).splitlines()[0]},
                "device": str(device)}
    write_json(out_dir / "manifest.json", manifest)
    return {"shard": shard, "records": len(records), "records_sha256": sha256(raw)}


def curve(records: list[dict], arm: str) -> dict:
    if arm not in ARMS or not records:
        raise ValueError("invalid mc3 arm or no records")
    out = {}
    for index, qp in enumerate(QPS):
        if any(row["measurements"][index]["qp"] != qp for row in records):
            raise ValueError("mc3 QP order differs")
        points = [row["measurements"][index][arm] for row in records]
        out[str(qp)] = {"n": len(records),
                        "bpp": float(np.mean([p["bpp"] for p in points])),
                        "top1": float(np.mean([p["correct"] for p in points]))}
    return out


def summarize(records: list[dict], anchor_arm: str, trial_arm: str,
              resamples: np.ndarray) -> dict:
    anchor, trial = curve(records, anchor_arm), curve(records, trial_arm)
    point = compare_curves(anchor, trial)
    samples = {key: [] for key in ("bd_rate_top1_pct", "bd_accuracy_top1_pp")}
    for indices in resamples:
        picked = [records[i] for i in indices]
        values = compare_curves(curve(picked, anchor_arm), curve(picked, trial_arm))
        for key in samples:
            if values[key] is not None and np.isfinite(values[key]):
                samples[key].append(values[key])
    intervals = {key: {"valid_draws": len(values), "requested_draws": len(resamples),
                       "ci95": np.percentile(values, [2.5, 97.5]).tolist()
                       if values else None}
                 for key, values in samples.items()}
    return {"n": len(records), "model": "mc3_18",
            "anchor_arm": anchor_arm, "trial_arm": trial_arm,
            "anchor_curve": anchor, "trial_curve": trial,
            "metrics": point, "bootstrap": intervals}


def merge(shard_dirs: list[Path], out: Path) -> dict:
    if len(shard_dirs) != SHARDS or out.exists():
        raise ValueError("four distinct shard directories and fresh output required")
    head = preregistered_head()
    selection, selection_sha = frozen_selection()
    bundles = {}
    for folder in shard_dirs:
        manifest_path, raw = folder / "manifest.json", folder / "shard_records.jsonl"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shard = manifest.get("shard")
        if shard in bundles or shard not in range(SHARDS):
            raise ValueError("duplicate/invalid mc3 shard")
        expected = selection["sources"][shard::SHARDS]
        records = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()]
        if (manifest.get("experiment") != EXPERIMENT or manifest.get("codec") != "h265"
                or manifest.get("stage") != "mc3" or manifest.get("shards") != SHARDS
                or manifest.get("n") != 50 or manifest.get("source_ids") !=
                [r["sequence_id"] for r in expected]
                or manifest.get("shard_fingerprint") !=
                digest([r["sequence_id"] for r in expected])
                or manifest.get("source_fingerprint") != selection["source_fingerprint"]
                or manifest.get("selection_sha256") != selection_sha
                or manifest.get("preregistration_commit") != PREREG_COMMIT
                or manifest.get("code_commit") != head
                or manifest.get("records_sha256") != sha256(raw)
                or manifest.get("qps") != list(QPS)
                or manifest.get("bootstrap_seed") != SEED
                or manifest.get("bootstrap_draws") != DRAWS
                or len(records) != 50):
            raise ValueError("incomplete or mismatched mc3 shard")
        categories = kinetics_category_index("mc3_18")
        for record, source in zip(records, expected, strict=True):
            label = categories[_canon(source["sequence_id"].split("/")[0])]
            validate_record(record, source, label)
        bundles[shard] = (manifest, records, sha256(raw))
    if set(bundles) != set(range(SHARDS)):
        raise ValueError("missing mc3 shard")
    rows_by_id = {row["sequence_id"]: row for _m, rows, _h in bundles.values()
                  for row in rows}
    ids = [r["sequence_id"] for r in selection["sources"]]
    if len(rows_by_id) != 200 or set(rows_by_id) != set(ids):
        raise ValueError("mc3 shards overlap or omit DEV source")
    ordered = [rows_by_id[key] for key in ids]
    rng = np.random.default_rng(SEED)
    resamples = rng.integers(0, len(ordered), (DRAWS, len(ordered)))
    comparisons = {name: summarize(ordered, anchor, trial, resamples)
                   for name, anchor, trial in COMPARISONS}
    report = {"experiment": EXPERIMENT, "scope": "exploratory reused DEV; no independent holdout",
              "codec": "h265", "n": 200,
              "source_fingerprint": selection["source_fingerprint"],
              "source_plan_sha256": PLAN_SHA256,
              "selection_sha256": selection_sha,
              "v7_result_sha256": V7_RESULT_SHA256,
              "preregistration_commit": PREREG_COMMIT,
              "analysis_code_commit": head,
              "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
              "bootstrap_unit": "source video; all QPs and three arms paired",
              "shard_manifests": [bundles[i][0] for i in range(SHARDS)],
              "shard_records_sha256": [bundles[i][2] for i in range(SHARDS)],
              "comparisons": comparisons}
    write_json(out, report)
    out.with_suffix(".sha256").write_text(f"{sha256(out)}  {out.name}\n",
                                               encoding="ascii")
    return {"result_sha256": sha256(out),
            "V7_vs_V6_bd_rate_top1_pct":
            comparisons["V7_vs_V6"]["metrics"]["bd_rate_top1_pct"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    prepare = subs.add_parser("prepare")
    prepare.add_argument("--cache-root", type=Path, required=True)
    prepare.add_argument("--pixel-root", type=Path, required=True)
    prepare.add_argument("--out", type=Path, required=True)
    shard = subs.add_parser("shard")
    shard.add_argument("--source-root", type=Path, required=True)
    shard.add_argument("--shard", type=int, choices=range(SHARDS), required=True)
    shard.add_argument("--out-dir", type=Path, required=True)
    merged = subs.add_parser("merge")
    merged.add_argument("--shard-dir", type=Path, action="append", required=True)
    merged.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare_selection(args.cache_root, args.pixel_root, args.out)
    elif args.command == "shard":
        result = run_shard(args.source_root, args.shard, args.out_dir)
    else:
        result = merge(args.shard_dir, args.out)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
