#!/usr/bin/env python
"""One-shot V6 confirmation on a new, committed source-disjoint holdout.

Primary shards encode all six candidates and score the two development
analyzers. mc3 shards score identity, V2-C and the V6-selected stream.
Merge builds whole-1,000-source curves before bootstrap.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torchvision

from ops.codec_search_ar import QPS
from ops.dual_codec_search import (bootstrap, collect, digest, metrics, prepare,
                                   selected_arrays, validate_row, write_json)
from ops.dual_codec_search_confirm_1000 import CONFIG as V2_CONFIG, load_frozen
from ops.lock_v6_holdout import (IDS_REL, INDEX_REL, REPO, SOURCES_REL,
                                 committed_lock, git, sha256)
from ops.paper_heldout_mc3 import compare as mc3_compare, timed_inference
from ops.paper_holdout_confirm import gate_this_codec, put_manifest, write_records
from ops.paper_validation import fixed_arrays
from ops.prepare_v6_holdout import v2_holdout_ids, v4_holdout_ids
from ops.rcts_pilot import clip_id
from ops.v6_dev_residual import predicted_measurements, selected_arrays_v6, select_residual
from ops.v6_frozen import MANIFEST, frozen_manifest, load_frozen_v6
from src.codecs.standard import StandardCodec, ffmpeg_available
from src.data.video_dataset import VideoClipDataset
from src.models.codec_search import CANDIDATES, make_candidates, normalized_bpp
from src.models.dual_codec_search import (MODELS, observations, risk_scores,
                                          select_observations)
from src.tasks.action_recognition import ActionRecognitionAnalyzer, kinetics_categories

EXPERIMENT = "v6_new_source_disjoint_holdout"
PREREG = REPO / "docs/PREREGISTRATION_V6_HOLDOUT.md"
SPLIT = REPO / "docs/HOLDOUT_SPLIT_V6.md"
SEED = 20261001
DRAWS = 2000
BASELINES = ("area96", "area112")
LOCKED_CODE = ("ops/paper_holdout_v6.py", "ops/v6_dev_residual.py",
               "ops/v6_frozen.py", "ops/lock_v6_holdout.py",
               "ops/prepare_v6_holdout.py", "ops/dual_codec_search.py",
               "ops/paper_heldout_mc3.py", "src/metrics/bd_rate.py")


def ready_index(index_path: Path, prereg_commit: str,
                video_root: Path) -> tuple[dict, VideoClipDataset]:
    if (len(prereg_commit) != 40 or
            any(c not in "0123456789abcdef" for c in prereg_commit)):
        raise ValueError("full V6 preregistration/index commit required")
    subprocess.run(["git", "-c", f"safe.directory={REPO.as_posix()}",
                    "merge-base", "--is-ancestor", prereg_commit, "HEAD"],
                   cwd=REPO, check=True)
    frozen = frozen_manifest()
    if frozen["preregistration_commit"] != "385674ddf93d477d78f0b6b1b4abdff667eee7e5":
        raise ValueError("V6 preregistration commit changed")
    if (git("show", f"{frozen['preregistration_commit']}:"
                    "docs/PREREGISTRATION_V6_HOLDOUT.md")
            != PREREG.read_bytes().replace(b"\r\n", b"\n")):
        raise ValueError("V6 preregistration changed after initial lock")
    for rel, path in (("docs/PREREGISTRATION_V6_HOLDOUT.md", PREREG),
                      ("docs/HOLDOUT_SPLIT_V6.md", SPLIT),
                      (INDEX_REL, index_path),
                      ("configs/v6_frozen/manifest.json", MANIFEST)):
        if git("show", f"{prereg_commit}:{rel}") != path.read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"V6 protocol/index differs from commit: {rel}")
    for rel in LOCKED_CODE:
        if git("show", f"{prereg_commit}:{rel}") != (
                REPO / rel).read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"V6 evaluation code differs from commit: {rel}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    meta = index["meta"]
    ids, sources = committed_lock(meta["locked_commit"],
                                  REPO / IDS_REL, REPO / SOURCES_REL)
    rows = index.get("test", [])
    if (len(rows) != 1000 or [row["source_id"] for row in rows] != ids
            or set(ids) & (v2_holdout_ids() | v4_holdout_ids())
            or meta["selected_source_fingerprint"] !=
               sources["selected_source_fingerprint"]
            or meta["selected_sources_sha256"] != sha256(REPO / SOURCES_REL)
            or meta["clips"] != 1000):
        raise ValueError("V6 index is not the locked new 1,000-source holdout")
    candidate_ids = (REPO / "configs/v6_holdout_source_audit/candidate_ids.txt")
    if (sha256(candidate_ids) != sources["candidate_ids_sha256"]
            or not set(ids).issubset(set(candidate_ids.read_text().splitlines()))):
        raise ValueError("V6 selected IDs are outside the locked candidate plan")
    resolved = []
    for row, source in zip(rows, sources["selected"]):
        if row["path"] != f"videos/{source['filename']}":
            raise ValueError("V6 index has changed video path")
        path = video_root / row["path"]
        if (not path.is_file() or path.stat().st_size != source["bytes"]
                or sha256(path) != source["video_sha256"]):
            raise ValueError(f"V6 video bytes differ from source lock: {row['source_id']}")
        resolved.append(str(path.resolve()))
    design = frozen["design"]
    if (design["qps"] != list(QPS) or design["candidates"] != list(CANDIDATES)
            or design["primary_analyzers"] != list(MODELS)
            or design["transfer_analyzer"] != "mc3_18"):
        raise ValueError("V6 codec/analyzer design changed")
    dataset = VideoClipDataset(index_path, split="test", num_frames=design["frames"],
                               frame_size=design["frame_size"],
                               temporal_stride=design["temporal_stride"],
                               train=False, return_metadata=True)
    for row, path in zip(dataset.samples, resolved):
        row["path"] = path
    return design, dataset


def manifest_base(index_path: Path, prereg_commit: str,
                  dataset: VideoClipDataset, codec: str, shard: int) -> dict:
    frozen = frozen_manifest()
    if codec != "h265":
        raise ValueError("V6 freeze covers H.265 only")
    cfg = frozen
    indices = [i for i in range(1000) if i % 2 == shard]
    meta = json.loads(index_path.read_text(encoding="utf-8"))["meta"]
    return {"experiment": EXPERIMENT, "codec": codec,
            "shard": shard, "shards": 2, "n": 500,
            "sample_ids": [clip_id(dataset.samples[i]) for i in indices],
            "source_ids": [dataset.samples[i]["source_id"] for i in indices],
            "source_fingerprint": meta["selected_source_fingerprint"],
            "index_sha256": sha256(index_path),
            "selected_sources_sha256": sha256(REPO / SOURCES_REL),
            "preregistration_commit": prereg_commit,
            "preregistration_sha256": sha256(PREREG),
            "freeze_manifest_sha256": sha256(MANIFEST),
            "dev_result_sha256": cfg["development_result_sha256"],
            "model_sha256": cfg["model_sha256"],
            "v2_comparator_policy_sha256_bytes": cfg["v2_policy_sha256_bytes"],
            "v2_comparator_risk_sha256_bytes": cfg["v2_risk_sha256_bytes"],
            "policy": cfg["policy"], "policy_digest": cfg["policy_digest"],
            "code_commit": git("rev-parse", "HEAD").decode().strip(),
            "qps": list(QPS), "candidates": list(CANDIDATES),
            "primary_analyzers": list(MODELS), "transfer_analyzer": "mc3_18",
            "bootstrap_unit": "source video; all QPs, arms and analyzers paired",
            "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
            "inference_seed": 53,
            "versions": {"python": platform.python_version(),
                         "torch": torch.__version__,
                         "torchvision": torchvision.__version__}}


def load_shard(path: Path, stage: str, codec: str, shard: int) -> tuple[dict, list]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    records = [json.loads(line) for line in
               (path / "shard_records.jsonl").read_text(encoding="utf-8").splitlines()]
    if (manifest["experiment"] != EXPERIMENT or manifest["stage"] != stage
            or manifest["codec"] != codec or manifest["shard"] != shard
            or len(records) != 500
            or [row["sequence_id"] for row in records] != manifest["sample_ids"]):
        raise ValueError("incomplete or mismatched V6 holdout shard")
    return manifest, records


def primary(args) -> None:
    if not ffmpeg_available():
        raise ValueError("ffmpeg and ffprobe required")
    design, dataset = ready_index(args.index, args.prereg_commit, args.video_root)
    manifest = {**manifest_base(args.index, args.prereg_commit,
                                dataset, args.codec, args.shard),
                "stage": "primary_six_candidate"}
    put_manifest(args.out_dir, manifest)
    torch.manual_seed(53)
    torch.set_num_threads(2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    analyzers = {name: ActionRecognitionAnalyzer(name, clip_size=112).freeze().to(device)
                 for name in MODELS}
    codec = StandardCodec(args.codec, preset=design["preset"], strict_decode=True)
    indices = [i for i in range(1000) if i % 2 == args.shard]
    rows = collect(dataset, indices, analyzers, codec, args.out_dir,
                   "holdout_primary_v6", digest(manifest))
    write_records(args.out_dir / "shard_records.jsonl", rows)
    print(f"[V6 primary] {args.codec} shard={args.shard} records={len(rows)}")


def selected_names(cache: dict, state: dict, old_policy: dict,
                   models: dict, policy: dict) -> list[tuple[str, str]]:
    """Choose both streams without reading labels or correctness outcomes."""
    prepared = predicted_measurements([cache], state, old_policy, models)[0]
    return [(measurement["candidates"][base]["name"],
             measurement["candidates"][select_residual(obs, base, probabilities,
                                                          policy)]["name"])
            for measurement, obs, base, probabilities in prepared]


def evaluate_mc3_clip(dataset: VideoClipDataset, index: int, cache: dict,
                      state: dict, old_policy: dict, models: dict, policy: dict,
                      analyzer: ActionRecognitionAnalyzer,
                      codec: StandardCodec) -> dict:
    source, label, meta = dataset[index]
    if meta["sequence_id"] != cache["sequence_id"]:
        raise ValueError("V6 primary and mc3 video IDs disagree")
    cap = cv2.VideoCapture(dataset.samples[index]["path"])
    ok, _ = cap.read()
    cap.release()
    if not ok:
        raise ValueError(f"undecodable V6 source: {meta['sequence_id']}")
    rgb = (source.permute(1, 2, 3, 0).numpy() * 255).round().astype(np.uint8)
    variants = make_candidates(rgb)
    measurements = []
    for item, (v2_name, v6_name) in zip(
            cache["measurements"], selected_names(cache, state, old_policy,
                                                   models, policy)):
        qp = item["qp"]
        streams = {}
        for arm, name in (("identity", "identity128"), ("v2", v2_name),
                          ("v6", v6_name)):
            if name in streams:
                reused = dict(streams[name])
                reused.update({"encode_decode_s": 0.0, "inference_s": 0.0,
                               "reused_from": name})
                streams[arm] = reused
                continue
            candidate = variants[name]
            _t, h, w, _ = candidate.shape
            start = time.perf_counter()
            reconstructed, native_bpp = codec._encode_decode_clip(candidate, qp=qp)
            encode_decode_s = time.perf_counter() - start
            prediction, inference_s = timed_inference(analyzer, reconstructed)
            value = {"name": name, "bpp": normalized_bpp(native_bpp, h, w),
                     "correct": bool(prediction == label),
                     "encode_decode_s": encode_decode_s,
                     "inference_s": inference_s,
                     "cached_bpp": next(row["bpp"] for row in item["candidates"]
                                        if row["name"] == name)}
            streams[name] = value
            streams[arm] = value
        measurements.append({"qp": qp, "v2_name": v2_name, "v6_name": v6_name,
                             "identity": streams["identity"],
                             "v2": streams["v2"], "v6": streams["v6"]})
    return {"sequence_id": meta["sequence_id"], "measurements": measurements}


def mc3(args) -> None:
    if not ffmpeg_available():
        raise ValueError("ffmpeg and ffprobe required")
    design, dataset = ready_index(args.index, args.prereg_commit, args.video_root)
    if kinetics_categories("mc3_18") != kinetics_categories("r3d_18"):
        raise ValueError("mc3 Kinetics labels differ")
    policy, models = load_frozen_v6()
    config = json.loads(V2_CONFIG.read_text(encoding="utf-8"))
    state, _frozen, old_policy = load_frozen(args.codec, config)
    primary_manifest, primary_rows = load_shard(
        args.primary_dir, "primary_six_candidate", args.codec, args.shard)
    manifest = {**manifest_base(args.index, args.prereg_commit,
                                dataset, args.codec, args.shard),
                "stage": "mc3_identity_v2_v6_selected_streams",
                "primary_records_sha256": sha256(args.primary_dir / "shard_records.jsonl")}
    for key in ("sample_ids", "source_ids", "index_sha256", "policy_digest",
                "model_sha256", "preregistration_commit", "source_fingerprint",
                "code_commit", "freeze_manifest_sha256"):
        if primary_manifest[key] != manifest[key]:
            raise ValueError(f"V6 mc3/primary provenance differs: {key}")
    put_manifest(args.out_dir, manifest)
    by_id = {row["sequence_id"]: row for row in primary_rows}
    torch.manual_seed(53)
    torch.set_num_threads(2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    analyzer = ActionRecognitionAnalyzer("mc3_18", clip_size=112).freeze().to(device)
    codec = StandardCodec(args.codec, preset=design["preset"], strict_decode=True)
    records = []
    for number, index in enumerate(i for i in range(1000) if i % 2 == args.shard):
        key = clip_id(dataset.samples[index])
        cache = by_id[key]
        validate_row(cache, key, args.codec, digest(primary_manifest))
        path = args.out_dir / "cache" / f"clip_{number:04d}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
        else:
            record = evaluate_mc3_clip(dataset, index, cache, state, old_policy,
                                       models, policy,
                                       analyzer, codec)
            for item in record["measurements"]:
                for arm in ("identity", "v2", "v6"):
                    if abs(item[arm]["bpp"] - item[arm]["cached_bpp"]) > 1e-9:
                        raise ValueError("V6 mc3 re-encode differs from primary cache")
            write_json(path, record)
        if (record["sequence_id"] != key
                or [item["qp"] for item in record["measurements"]] != list(QPS)):
            raise ValueError("stale V6 mc3 video cache")
        names = selected_names(cache, state, old_policy, models, policy)
        for item, expected_names, primary_item in zip(
                record["measurements"], names, cache["measurements"]):
            if (item["v2_name"], item["v6_name"]) != expected_names:
                raise ValueError("stale V6 mc3 selected streams")
            for arm, name in (("identity", "identity128"),
                              ("v2", expected_names[0]),
                              ("v6", expected_names[1])):
                cached = next(row["bpp"] for row in primary_item["candidates"]
                              if row["name"] == name)
                if (item[arm]["name"] != name
                        or abs(item[arm]["bpp"] - cached) > 1e-9):
                    raise ValueError("stale V6 mc3 bpp/stream")
        records.append(record)
        print(f"[V6 mc3] {args.codec} shard={args.shard} {number + 1}/500",
              flush=True)
    write_records(args.out_dir / "shard_records.jsonl", records)


def merged_rows(paths: list[Path], stage: str, codec: str,
                expected: dict) -> tuple[list, list]:
    if len(paths) != 2:
        raise ValueError("exactly two V6 shard directories required")
    bundles = [load_shard(path, stage, codec, shard)
               for shard, path in enumerate(paths)]
    for shard, (manifest, _) in enumerate(bundles):
        for key in ("index_sha256", "preregistration_commit", "source_fingerprint",
                    "policy_digest", "freeze_manifest_sha256", "model_sha256",
                    "bootstrap_seed", "bootstrap_draws", "code_commit"):
            if manifest[key] != expected[key]:
                raise ValueError(f"V6 shard provenance mismatch: {key}")
        if (manifest["sample_ids"] != expected["all_sample_ids"][shard::2]
                or manifest["source_ids"] != expected["all_source_ids"][shard::2]):
            raise ValueError("V6 shard IDs differ from locked index")
    by_id = {row["sequence_id"]: row for _, rows in bundles for row in rows}
    if len(by_id) != 1000:
        raise ValueError("V6 merge requires 1,000 distinct sources")
    return [by_id[key] for key in expected["all_sample_ids"]], [m for m, _ in bundles]


def mc3_curve(records: list[dict], arm: str) -> dict:
    if arm not in {"identity", "v2", "v6"} or not records:
        raise ValueError("invalid mc3 arm or empty records")
    curve = {}
    for position, qp in enumerate(QPS):
        if any(row["measurements"][position]["qp"] != qp for row in records):
            raise ValueError("mc3 QP order changed")
        values = [row["measurements"][position][arm] for row in records]
        curve[str(qp)] = {"n": len(records),
                          "bpp": float(np.mean([value["bpp"] for value in values])),
                          "top1": float(np.mean([value["correct"] for value in values]))}
    return curve


def summarize_mc3_v6(records: list[dict], anchor_arm: str,
                     trial_arm: str) -> dict:
    anchor, trial = mc3_curve(records, anchor_arm), mc3_curve(records, trial_arm)
    point = mc3_compare(anchor, trial)
    rng = np.random.default_rng(SEED)
    samples = {key: [] for key in ("bd_rate_top1_pct", "bd_accuracy_top1_pp")}
    for _ in range(DRAWS):
        picked = [records[i] for i in rng.integers(0, len(records), len(records))]
        a, b = mc3_curve(picked, anchor_arm), mc3_curve(picked, trial_arm)
        metric = mc3_compare(a, b)
        for key, values in samples.items():
            if np.isfinite(metric[key]):
                values.append(metric[key])
    intervals = {key: {"valid_draws": len(values), "requested_draws": DRAWS,
                       "ci95": np.percentile(values, [2.5, 97.5]).tolist()
                       if values else None}
                 for key, values in samples.items()}
    return {"n": len(records), "model": "mc3_18", "anchor_arm": anchor_arm,
            "trial_arm": trial_arm, "anchor_curve": anchor,
            "trial_curve": trial, "metrics": point, "bootstrap": intervals,
            "bootstrap_seed": SEED,
            "bootstrap_unit": "source video; QPs and arms paired"}


def merge(args) -> None:
    _design, dataset = ready_index(args.index, args.prereg_commit, args.video_root)
    policy, models = load_frozen_v6()
    config = json.loads(V2_CONFIG.read_text(encoding="utf-8"))
    state, _frozen, old_policy = load_frozen(args.codec, config)
    expected = {**manifest_base(args.index, args.prereg_commit,
                                 dataset, args.codec, 0),
                "all_sample_ids": [clip_id(row) for row in dataset.samples],
                "all_source_ids": [row["source_id"] for row in dataset.samples]}
    primary_rows, primary_manifests = merged_rows(
        args.primary_dir, "primary_six_candidate", args.codec, expected)
    mc3_rows, mc3_manifests = merged_rows(
        args.mc3_dir, "mc3_identity_v2_v6_selected_streams", args.codec, expected)
    if [r["sequence_id"] for r in primary_rows] != [r["sequence_id"] for r in mc3_rows]:
        raise ValueError("V6 primary and mc3 videos are not paired")
    old_prepared = prepare(primary_rows, state)
    identity, _ = selected_arrays(old_prepared, {"mode": "identity"})
    old, old_choices = selected_arrays(old_prepared, old_policy)
    prepared = predicted_measurements(primary_rows, state, old_policy, models)
    new, _new_distances, new_choices = selected_arrays_v6(prepared, policy)
    for raw, independent in zip(primary_rows, mc3_rows):
        names = selected_names(raw, state, old_policy, models, policy)
        for item, check, (v2_name, v6_name) in zip(
                raw["measurements"], independent["measurements"], names):
            if (check["qp"] != item["qp"] or check["v2_name"] != v2_name
                    or check["v6_name"] != v6_name):
                raise ValueError("mc3 stream differs from frozen selection")
            for arm, name in (("identity", "identity128"), ("v2", v2_name),
                              ("v6", v6_name)):
                cached = next(row["bpp"] for row in item["candidates"]
                              if row["name"] == name)
                if (check[arm]["name"] != name
                        or abs(check[arm]["bpp"] - cached) > 1e-9):
                    raise ValueError("mc3 stream/bpp differs from primary cache")
    arms = {"V2-C": (old, old_choices), "V6": (new, new_choices)}
    for name in BASELINES:
        arms[name] = fixed_arrays(primary_rows, name)
    comparisons = {}
    for name, (array, choices) in arms.items():
        comparisons[f"{name}_vs_identity"] = {
            "analyzers": metrics(identity, array),
            "bootstrap": bootstrap(identity, array, DRAWS, SEED),
            "choices": choices}
    comparisons["V6_vs_V2-C"] = {"analyzers": metrics(old, new),
                                  "bootstrap": bootstrap(old, new, DRAWS, SEED)}
    for name in BASELINES:
        comparisons[f"V6_vs_{name}"] = {
            "analyzers": metrics(arms[name][0], new),
            "bootstrap": bootstrap(arms[name][0], new, DRAWS, SEED)}
    report = {"experiment": EXPERIMENT, "codec": args.codec, "n": 1000,
              "source_fingerprint": expected["source_fingerprint"],
              "index_sha256": expected["index_sha256"],
              "freeze_manifest_sha256": expected["freeze_manifest_sha256"],
              "preregistration_commit": args.prereg_commit,
              "analysis_code_commit": git("rev-parse", "HEAD").decode().strip(),
              "bootstrap_unit": expected["bootstrap_unit"],
              "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
              "policy": policy, "policy_digest": digest(policy),
              "model_sha256": expected["model_sha256"],
              "point_gate_this_codec": gate_this_codec(
                  comparisons["V6_vs_identity"]["analyzers"]),
              "primary_shard_manifests": primary_manifests,
              "mc3_shard_manifests": mc3_manifests,
              "raw_record_sha256": {
                  "primary": [sha256(path / "shard_records.jsonl")
                              for path in args.primary_dir],
                  "mc3": [sha256(path / "shard_records.jsonl")
                          for path in args.mc3_dir]},
              "comparisons": comparisons,
              "mc3": {
                  "V2-C_vs_identity": summarize_mc3_v6(mc3_rows, "identity", "v2"),
                  "V6_vs_identity": summarize_mc3_v6(mc3_rows, "identity", "v6"),
                  "V6_vs_V2-C": summarize_mc3_v6(mc3_rows, "v2", "v6")}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, report)
    args.out.with_suffix(".sha256").write_text(
        f"{sha256(args.out)}  {args.out.name}\n", encoding="utf-8")
    print(f"[V6 merge] {args.codec} 1,000 paired source videos")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("primary", "mc3", "merge"):
        p = sub.add_parser(command)
        p.add_argument("--index", type=Path, required=True)
        p.add_argument("--video-root", type=Path, required=True)
        p.add_argument("--prereg-commit", required=True)
        p.add_argument("--codec", choices=("h265",), required=True)
        if command == "merge":
            p.add_argument("--primary-dir", type=Path, action="append", required=True)
            p.add_argument("--mc3-dir", type=Path, action="append", required=True)
            p.add_argument("--out", type=Path, required=True)
        else:
            p.add_argument("--shard", type=int, choices=(0, 1), required=True)
            p.add_argument("--out-dir", type=Path, required=True)
            if command == "mc3":
                p.add_argument("--primary-dir", type=Path, required=True)
    args = parser.parse_args()
    {"primary": primary, "mc3": mc3, "merge": merge}[args.command](args)


if __name__ == "__main__":
    main()
