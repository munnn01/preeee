#!/usr/bin/env python
"""Frozen V6 plus fixed chroma-only pre-codec edit, on reused CAL sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np

from ops.codec_search_ar import QPS, as_video
from ops.dual_codec_search import digest, write_json
from ops.v5_dev_agreement import load_locked_dev_cache
from ops.v6_dev_residual import predicted_measurements, select_residual
from ops.v6_frozen import load_frozen_v6
from ops.v7_dev_transfer import load_cache_stage, load_proxy_stage
from ops.v7_pixel_proxy import find_planned_videos, sha256, verify_protocol
from ops.v8_motion_pilot import summarize
from src.codecs.standard import StandardCodec, ffmpeg_available
from src.data.video_dataset import VideoClipDataset
from src.models.codec_search import CANDIDATES, make_candidates, normalized_bpp
from src.tasks.action_recognition import (
    ActionRecognitionAnalyzer, _canon, kinetics_categories,
    kinetics_category_index,
)

REPO = Path(__file__).resolve().parents[1]
PREREG = REPO / "docs/PREREGISTRATION_V9_CHROMA_CAL.md"
PREREG_COMMIT = "56485c739e257de74b1e40d658ec77302973fd03"
PLAN_SHA256 = "5b0a32d1d0a1759b50232f0c297ee35ee5cfe0cfdf00c53b587781baa5afebc2"
V7_PIXEL_CODE_COMMIT = "2c0a29836101fced7a91b7ff136a8b929b6d7c2b"
V7_CAL_PIXEL_SHA256 = "c7e62d72b97cf7bcdc739008ad1d95dddc8c75f7e75e8a577cc2517222e1d2d0"
EXPERIMENT = "v9_chroma_h265_reused_cal_development"
SELECTION = REPO / "configs/v9_chroma_cal_selection.json"
MODELS = ("r2plus1d_18", "r3d_18", "mc3_18")
ARMS = ("identity", "v6", "v9")
COMPARISONS = (
    ("V6_vs_identity", "identity", "v6"),
    ("V9_vs_identity", "identity", "v9"),
    ("V9_vs_V6", "v6", "v9"),
)
SHARDS = 4
N = 100
SEED = 20261006
DRAWS = 2000


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", *args], cwd=REPO
    )


def protocol() -> tuple[list[str], str, str]:
    git("merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD")
    locked = git("show", f"{PREREG_COMMIT}:docs/PREREGISTRATION_V9_CHROMA_CAL.md")
    if PREREG.read_bytes().replace(b"\r\n", b"\n") != locked:
        raise ValueError("V9 preregistration changed after lock")
    plan, _ = verify_protocol()
    ids = plan["stage_ids"]["calibration"][100:200]
    if len(ids) != N or len(set(ids)) != N:
        raise ValueError("invalid second CAL half")
    if sha256(REPO / "configs/v7_dev_proxy_plan.json") != PLAN_SHA256:
        raise ValueError("source plan SHA-256 changed")
    for relative in ("ops/v9_chroma_cal.py", "kaggle/v9_chroma_cal_cell.sh"):
        git("ls-files", "--error-unmatch", relative)
        subprocess.run(
            ["git", "-c", f"safe.directory={REPO.as_posix()}",
             "diff", "--quiet", "HEAD", "--", relative],
            cwd=REPO, check=True, capture_output=True,
        )
    head = git("rev-parse", "HEAD").decode().strip()
    return ids, head, hashlib.sha256(locked).hexdigest()


def chroma_blend(clip: np.ndarray) -> tuple[np.ndarray, float]:
    """Keep uint8 Y, blend Cr/Cb 50% toward Gaussian sigma 1.5."""
    if (clip.ndim != 4 or clip.shape[0] != 16 or clip.shape[-1] != 3
            or clip.dtype != np.uint8 or min(clip.shape[1:3]) < 16):
        raise ValueError("expected uint8 RGB [16,H,W,3] with H,W>=16")
    output = np.empty_like(clip)
    errors = []
    for i, frame in enumerate(clip):
        ycc = cv2.cvtColor(frame, cv2.COLOR_RGB2YCrCb)
        edited = ycc.copy()
        for channel in (1, 2):
            blurred = cv2.GaussianBlur(ycc[:, :, channel], (0, 0), 1.5)
            edited[:, :, channel] = np.rint(
                0.5 * ycc[:, :, channel].astype(np.float32)
                + 0.5 * blurred.astype(np.float32)
            ).astype(np.uint8)
        output[i] = cv2.cvtColor(edited, cv2.COLOR_YCrCb2RGB)
        roundtrip = cv2.cvtColor(output[i], cv2.COLOR_RGB2YCrCb)
        errors.append(float(np.abs(roundtrip[:, :, 0].astype(np.int16)
                                   - ycc[:, :, 0].astype(np.int16)).mean()))
    return output, float(np.mean(errors))


def prepare_selection(cache_root: Path, pixel_root: Path, out: Path) -> dict:
    if out.exists():
        raise ValueError("selection path must be fresh")
    ids, head, prereg_sha = protocol()
    plan, _ = verify_protocol()
    lock, lock_sha = load_locked_dev_cache()
    rows, risk, v2_policy = load_cache_stage(cache_root, "calibration", plan, lock)
    pixels, pixel_hashes = load_proxy_stage(
        pixel_root, "calibration", plan, V7_PIXEL_CODE_COMMIT
    )
    if pixel_hashes["records_sha256"] != V7_CAL_PIXEL_SHA256:
        raise ValueError("prior CAL source hash record changed")
    v6_policy, models = load_frozen_v6()
    selected_rows = rows[100:200]
    prepared = predicted_measurements(selected_rows, risk, v2_policy, models)
    sources = []
    for key, row, video in zip(ids, selected_rows, prepared, strict=True):
        if row["sequence_id"] != key:
            raise ValueError("V2 CAL cache order changed")
        measurements = []
        for measurement, observations, base, probabilities in video:
            chosen = select_residual(observations, base, probabilities, v6_policy)
            name = observations[chosen]["name"]
            if name not in CANDIDATES:
                raise ValueError("unexpected frozen V6 candidate")
            measurements.append({
                "qp": measurement["qp"],
                "identity": "identity128", "v6": name,
                "cached_bpp": {
                    "identity": float(measurement["candidates"][0]["bpp"]),
                    "v6": float(measurement["candidates"][chosen]["bpp"]),
                },
            })
        sources.append({
            "sequence_id": key, "source_sha256": pixels[key]["source_sha256"],
            "measurements": measurements,
        })
    selection = {
        "experiment": EXPERIMENT, "scope": "reused V2 CAL; development only",
        "codec": "h265", "qps": list(QPS), "shards": SHARDS, "n": N,
        "source_ids": ids, "source_fingerprint": digest(ids),
        "source_plan_sha256": PLAN_SHA256,
        "v2_cache_lock_sha256": lock_sha,
        "v7_cal_pixel_records_sha256": V7_CAL_PIXEL_SHA256,
        "v7_cal_pixel_manifest_sha256": pixel_hashes["manifest_sha256"],
        "v6_frozen_manifest_sha256": sha256(REPO / "configs/v6_h265_frozen/manifest.json"),
        "v6_policy": v6_policy, "preregistration_commit": PREREG_COMMIT,
        "preregistration_sha256": prereg_sha, "generator_commit": head,
        "sources": sources,
    }
    write_json(out, selection)
    return {"n": N, "source_fingerprint": digest(ids),
            "selection_sha256": sha256(out)}


def frozen_selection() -> tuple[dict, str, str]:
    ids, head, prereg_sha = protocol()
    if SELECTION.read_bytes() != git("show", f"HEAD:{SELECTION.relative_to(REPO).as_posix()}"):
        raise ValueError("selection differs from committed Git bytes")
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    if (selection.get("experiment") != EXPERIMENT
            or selection.get("codec") != "h265"
            or selection.get("qps") != list(QPS)
            or selection.get("shards") != SHARDS or selection.get("n") != N
            or selection.get("source_ids") != ids
            or selection.get("source_fingerprint") != digest(ids)
            or selection.get("source_plan_sha256") != PLAN_SHA256
            or selection.get("v7_cal_pixel_records_sha256") != V7_CAL_PIXEL_SHA256
            or selection.get("preregistration_commit") != PREREG_COMMIT
            or selection.get("preregistration_sha256") != prereg_sha
            or len(selection.get("sources", [])) != N):
        raise ValueError("V9 selection differs from preregistered inputs")
    for source, key in zip(selection["sources"], ids, strict=True):
        if (source.get("sequence_id") != key
                or len(source.get("source_sha256", "")) != 64
                or len(source.get("measurements", [])) != len(QPS)):
            raise ValueError("V9 source selection incomplete")
        for choice, qp in zip(source["measurements"], QPS, strict=True):
            if (choice.get("qp") != qp or choice.get("identity") != "identity128"
                    or choice.get("v6") not in CANDIDATES
                    or set(choice.get("cached_bpp", {})) != {"identity", "v6"}
                    or min(choice["cached_bpp"].values()) <= 0):
                raise ValueError("V9 QP choice incomplete")
    return selection, sha256(SELECTION), head


def decode_source(path: Path) -> np.ndarray:
    dataset = VideoClipDataset.__new__(VideoClipDataset)
    dataset.num_frames, dataset.frame_size = 16, 128
    dataset.temporal_stride, dataset.train = 2, False
    return dataset._read_clip(str(path))


def validate_record(record: dict, source: dict, label: int) -> None:
    if (record.get("sequence_id") != source["sequence_id"]
            or record.get("source_sha256") != source["source_sha256"]
            or record.get("label") != label
            or len(record.get("measurements", [])) != len(QPS)):
        raise ValueError("stale or incomplete V9 source record")
    for measurement, choice in zip(record["measurements"], source["measurements"], strict=True):
        if (measurement.get("qp") != choice["qp"]
                or set(measurement.get("arms", {})) != set(ARMS)
                or not np.isfinite(measurement.get("y_roundtrip_mae", float("nan")))):
            raise ValueError("incomplete V9 QP measurement")
        for arm in ARMS:
            row = measurement["arms"][arm]
            expected_name = ("v6_chroma050" if arm == "v9" else choice[arm])
            if (row.get("name") != expected_name
                    or row.get("coded_bytes", 0) <= 0 or row.get("bpp", 0) <= 0
                    or set(row.get("analyzers", {})) != set(MODELS)
                    or abs(row["bpp"] - 8 * row["coded_bytes"] / (16 * 128 * 128)) > 1e-9):
                raise ValueError("invalid V9 arm/bitrate record")
            if arm != "v9" and abs(row["bpp"] - choice["cached_bpp"][arm]) > 1e-9:
                raise ValueError("V2 cache bitrate mismatch")
            for model in MODELS:
                scored = row["analyzers"][model]
                prediction = scored.get("predicted_class_index")
                if (not isinstance(prediction, int) or not 0 <= prediction < 400
                        or scored.get("correct") is not (prediction == label)):
                    raise ValueError("inconsistent V9 analyzer outcome")


def evaluate_source(source: dict, path: Path, label: int,
                    analyzers: dict, codec: StandardCodec) -> dict:
    key = source["sequence_id"]
    if sha256(path) != source["source_sha256"]:
        raise ValueError(f"source video hash changed: {key}")
    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    if not ok:
        raise ValueError(f"undecodable CAL source: {key}")
    variants = make_candidates(decode_source(path))
    chroma = {name: chroma_blend(variants[name])
              for name in {choice["v6"] for choice in source["measurements"]}}
    import torch
    measurements = []
    for choice in source["measurements"]:
        qp = choice["qp"]
        streams = {
            "identity": (choice["identity"], variants["identity128"]),
            "v6": (choice["v6"], variants[choice["v6"]]),
            "v9": ("v6_chroma050", chroma[choice["v6"]][0]),
        }
        values = {}
        for arm, (name, candidate) in streams.items():
            _, h, w, _ = candidate.shape
            start = time.perf_counter()
            reconstructed, native_bpp = codec._encode_decode_clip(candidate, qp=qp)
            encode_s = time.perf_counter() - start
            coded_bytes = int(round(native_bpp * 16 * h * w / 8))
            scores = {}
            for model, analyzer in analyzers.items():
                if next(analyzer.parameters()).is_cuda:
                    torch.cuda.synchronize()
                start = time.perf_counter()
                with torch.no_grad():
                    video = as_video(reconstructed).to(next(analyzer.parameters()).device)
                    prediction = int(analyzer.predict(video).argmax(1).item())
                if next(analyzer.parameters()).is_cuda:
                    torch.cuda.synchronize()
                scores[model] = {
                    "predicted_class_index": prediction, "correct": prediction == label,
                    "inference_s": time.perf_counter() - start,
                }
            values[arm] = {
                "name": name, "coded_bytes": coded_bytes,
                "bpp": normalized_bpp(native_bpp, h, w),
                "encode_decode_s": encode_s, "analyzers": scores,
            }
        measurements.append({
            "qp": qp, "arms": values,
            "y_roundtrip_mae": chroma[choice["v6"]][1],
        })
    record = {
        "sequence_id": key, "source_sha256": source["source_sha256"],
        "label": label, "measurements": measurements,
    }
    validate_record(record, source, label)
    return record


def run_shard(root: Path, shard: int, out_dir: Path) -> dict:
    if shard not in range(SHARDS) or not root.is_dir() or not ffmpeg_available():
        raise ValueError("invalid source root/shard or missing FFmpeg")
    selection, selection_sha, head = frozen_selection()
    assigned = selection["sources"][shard::SHARDS]
    paths = find_planned_videos(root, [source["sequence_id"] for source in assigned])
    if any(kinetics_categories(m) != kinetics_categories(MODELS[0]) for m in MODELS):
        raise ValueError("Kinetics category order differs")
    categories = kinetics_category_index(MODELS[0])
    import torch
    import torchvision
    torch.manual_seed(53)
    torch.set_num_threads(2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    analyzers = {
        model: ActionRecognitionAnalyzer(model, clip_size=112).freeze().to(device)
        for model in MODELS
    }
    codec = StandardCodec("h265", preset="medium", strict_decode=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for number, source in enumerate(assigned, 1):
        key = source["sequence_id"]
        label = categories.get(_canon(key.split("/")[0]))
        if label is None:
            raise ValueError(f"unmapped Kinetics class: {key}")
        checkpoint = out_dir / "cache" / f"clip_{number:03d}.json"
        if checkpoint.exists():
            row = json.loads(checkpoint.read_text(encoding="utf-8"))
        else:
            row = evaluate_source(source, paths[key], label, analyzers, codec)
            write_json(checkpoint, row)
        validate_record(row, source, label)
        rows.append(row)
        print(f"[V9 chroma CAL] shard={shard} {number}/{len(assigned)}", flush=True)
    raw = out_dir / "shard_records.jsonl"
    raw.write_bytes("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
                            for row in rows).encode("utf-8"))
    manifest = {
        "experiment": EXPERIMENT, "scope": "reused CAL development only",
        "codec": "h265", "shard": shard, "shards": SHARDS, "n": len(rows),
        "source_ids": [s["sequence_id"] for s in assigned],
        "source_fingerprint": selection["source_fingerprint"],
        "source_plan_sha256": PLAN_SHA256, "selection_sha256": selection_sha,
        "preregistration_commit": PREREG_COMMIT,
        "preregistration_sha256": selection["preregistration_sha256"],
        "code_commit": head, "records_sha256": sha256(raw),
        "qps": list(QPS), "arms": list(ARMS), "analyzers": list(MODELS),
        "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
        "bootstrap_unit": "source video; all QPs, arms and analyzers paired",
        "versions": {
            "python": platform.python_version(), "torch": torch.__version__,
            "torchvision": torchvision.__version__, "opencv": cv2.__version__,
            "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
        },
        "device": str(device),
    }
    write_json(out_dir / "manifest.json", manifest)
    return {"shard": shard, "n": len(rows), "records_sha256": sha256(raw)}


def merge(shard_dirs: list[Path], out: Path) -> dict:
    if len(shard_dirs) != SHARDS or out.exists():
        raise ValueError("four shard folders and fresh output required")
    selection, selection_sha, head = frozen_selection()
    bundles = {}
    categories = kinetics_category_index(MODELS[0])
    for folder in shard_dirs:
        manifest_path, raw = folder / "manifest.json", folder / "shard_records.jsonl"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shard = manifest.get("shard")
        if shard in bundles or shard not in range(SHARDS):
            raise ValueError("duplicate/invalid V9 shard")
        expected = selection["sources"][shard::SHARDS]
        rows = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()]
        if (manifest.get("experiment") != EXPERIMENT or manifest.get("codec") != "h265"
                or manifest.get("shards") != SHARDS or manifest.get("n") != len(expected)
                or manifest.get("source_ids") != [s["sequence_id"] for s in expected]
                or manifest.get("source_fingerprint") != selection["source_fingerprint"]
                or manifest.get("source_plan_sha256") != PLAN_SHA256
                or manifest.get("selection_sha256") != selection_sha
                or manifest.get("preregistration_commit") != PREREG_COMMIT
                or manifest.get("preregistration_sha256") != selection["preregistration_sha256"]
                or manifest.get("code_commit") != head
                or manifest.get("records_sha256") != sha256(raw)
                or manifest.get("qps") != list(QPS)
                or manifest.get("arms") != list(ARMS)
                or manifest.get("analyzers") != list(MODELS)
                or manifest.get("bootstrap_seed") != SEED
                or manifest.get("bootstrap_draws") != DRAWS
                or len(rows) != len(expected)):
            raise ValueError("incomplete or mismatched V9 shard")
        for record, source in zip(rows, expected, strict=True):
            label = categories[_canon(source["sequence_id"].split("/")[0])]
            validate_record(record, source, label)
        bundles[shard] = (manifest, rows, sha256(raw))
    if set(bundles) != set(range(SHARDS)):
        raise ValueError("missing V9 shard")
    by_id = {r["sequence_id"]: r for _, rows, _ in bundles.values() for r in rows}
    ids = selection["source_ids"]
    if len(by_id) != N or set(by_id) != set(ids):
        raise ValueError("V9 source overlap/omission")
    ordered = [by_id[key] for key in ids]
    rng = np.random.default_rng(SEED)
    resamples = rng.integers(0, N, size=(DRAWS, N))
    comparisons = {
        name: {model: summarize(ordered, anchor, trial, model, resamples)
               for model in MODELS}
        for name, anchor, trial in COMPARISONS
    }
    direct = comparisons["V9_vs_V6"]
    trial = comparisons["V9_vs_identity"]
    mc3_rate = direct["mc3_18"]["metrics"]["bd_rate_top1_pct"]
    mc3_ci = direct["mc3_18"]["bootstrap"]["bd_rate_top1_pct"]["ci95"]
    go = (mc3_rate is not None and mc3_rate < 0 and mc3_ci is not None
          and mc3_ci[1] < 0)
    for model in MODELS[:2]:
        measured = trial[model]["metrics"]
        delta = direct[model]["metrics"]
        go = (go and measured["bd_rate_top1_pct"] is not None
              and measured["bd_rate_top1_pct"] < -10
              and measured["bd_accuracy_top1_pp"] is not None
              and measured["bd_accuracy_top1_pp"] > 0
              and delta["bd_rate_top1_pct"] is not None
              and delta["bd_rate_top1_pct"] <= 1.0)
    go = bool(go and all(
        direct[model]["metrics"]["min_same_qp_top1_gap_pp"] >= -1.0 - 1e-9
        for model in MODELS
    ))
    report = {
        "experiment": EXPERIMENT, "scope": "reused CAL development; no holdout",
        "codec": "h265", "n": N, "source_ids": ids,
        "source_fingerprint": selection["source_fingerprint"],
        "source_plan_sha256": PLAN_SHA256,
        "source_video_sha256": {key: by_id[key]["source_sha256"] for key in ids},
        "selection_sha256": selection_sha,
        "preregistration_commit": PREREG_COMMIT,
        "preregistration_sha256": selection["preregistration_sha256"],
        "analysis_code_commit": head, "bootstrap_seed": SEED,
        "bootstrap_draws": DRAWS,
        "bootstrap_unit": "source video; all QPs, arms and analyzers paired",
        "shard_manifests": [bundles[i][0] for i in range(SHARDS)],
        "shard_records_sha256": [bundles[i][2] for i in range(SHARDS)],
        "y_roundtrip_mae": {
            "mean": float(np.mean([
                m["y_roundtrip_mae"] for row in ordered for m in row["measurements"]
            ])),
            "max": float(max(
                m["y_roundtrip_mae"] for row in ordered for m in row["measurements"]
            )),
        },
        "comparisons": comparisons, "go_no_go": go,
        "original_confirmatory_gate": "NOT ASSESSED: reused CAL sources",
    }
    write_json(out, report)
    result_sha = sha256(out)
    out.with_suffix(".sha256").write_text(f"{result_sha}  {out.name}\n", encoding="ascii")
    return {"result_sha256": result_sha, "go_no_go": go}


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
