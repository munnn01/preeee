#!/usr/bin/env python
"""Time the full six-candidate V2 search against an identity-only pipeline.

Unlike paper_heldout_mc3, this benchmark includes every trial encode/decode
and both frozen analyzer passes needed by the selector. It excludes model
weight download and process startup, and uses a fixed, documented sample.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np
import torch
import torchvision

from ops.codec_search_ar import QPS, as_video, predict_and_feature
from ops.dual_codec_search import digest, signals, write_json
from ops.dual_codec_search_confirm_1000 import CONFIG, load_frozen
from ops.rcts_pilot import balanced_indices, clip_id
from src.codecs.standard import StandardCodec, ffmpeg_available
from src.data.video_dataset import VideoClipDataset
from src.models.codec_search import CANDIDATES, make_candidates, normalized_bpp
from src.models.dual_codec_search import MODELS, select
from src.tasks.action_recognition import ActionRecognitionAnalyzer


def measured_prediction(analyzer, video):
    if next(analyzer.parameters()).is_cuda:
        torch.cuda.synchronize()
    start = time.perf_counter()
    result = predict_and_feature(analyzer, video)
    if next(analyzer.parameters()).is_cuda:
        torch.cuda.synchronize()
    return result, time.perf_counter() - start


def identity_pipeline(rgb, codec):
    """Encoder baseline: no analyzer or selection work."""
    start = time.perf_counter()
    for qp in QPS:
        codec._encode_decode_clip(rgb, qp=qp)
    return time.perf_counter() - start


def full_pipeline(source, rgb, analyzers, codec, risk, policy):
    """All six trial encodes and both encoder-side analyzers at every QP."""
    full_start = time.perf_counter()
    start = time.perf_counter()
    variants = make_candidates(rgb)
    variants_s = time.perf_counter() - start
    clean, clean_s = {}, 0.0
    for model in MODELS:
        (logits, feature), elapsed = measured_prediction(analyzers[model], source[None])
        clean[model] = (logits.softmax(1), feature)
        clean_s += elapsed
    qps = []
    for qp in QPS:
        anchor, candidates = {}, []
        candidate_costs = []
        for name in CANDIDATES:
            candidate = variants[name]
            _t, h, w, _ = candidate.shape
            start = time.perf_counter()
            reconstructed, native_bpp = codec._encode_decode_clip(candidate, qp=qp)
            codec_s = time.perf_counter() - start
            row = {"name": name, "bpp": normalized_bpp(native_bpp, h, w),
                   "signals": {}}
            model_s = 0.0
            for model in MODELS:
                (logits, feature), elapsed = measured_prediction(
                    analyzers[model], as_video(reconstructed))
                model_s += elapsed
                if name == "identity128":
                    anchor[model] = (logits.softmax(1), feature)
                row["signals"][model] = signals(logits, feature, clean[model],
                                                  anchor[model])
            candidates.append(row)
            candidate_costs.append({"name": name, "codec_s": codec_s,
                                    "both_analyzers_s": model_s})
        start = time.perf_counter()
        chosen = select(candidates, qp, policy, risk)
        selector_s = time.perf_counter() - start
        qps.append({"qp": qp, "chosen": CANDIDATES[chosen],
                    "candidate_costs": candidate_costs, "selector_s": selector_s})
    return time.perf_counter() - full_start, variants_s, clean_s, qps


def measure_clip(dataset, index, analyzers, codec, risk, policy):
    """In-process timing helper kept for lightweight tests.

    The CLI uses isolated workers below so memory reflects each real arm.
    """
    start = time.perf_counter()
    source, _label, meta = dataset[index]
    rgb = (source.permute(1, 2, 3, 0).numpy() * 255).round().astype(np.uint8)
    decode_s = time.perf_counter() - start

    # Block by source clip; reverse the arm order for half of clips to reduce
    # systematic warm-up/drift bias. The seed is fixed and independent of results.
    reverse = int(hashlib.sha256(
        f"paper-runtime-order-20260924\0{meta['sequence_id']}".encode()
    ).hexdigest(), 16) % 2 == 1
    order = ("full", "identity") if reverse else ("identity", "full")
    elapsed = {}
    for arm in order:
        elapsed[arm] = (full_pipeline(source, rgb, analyzers, codec, risk, policy)
                        if arm == "full" else identity_pipeline(rgb, codec))
    full_s, variants_s, clean_s, qps = elapsed["full"]
    baseline_s = elapsed["identity"]
    return {"sequence_id": meta["sequence_id"], "decode_s": decode_s,
            "candidate_generation_s": variants_s, "clean_analyzers_s": clean_s,
            "arm_order": list(order), "qps": qps,
            "identity_codec_calls": len(QPS),
            "full_codec_calls": len(QPS) * len(CANDIDATES),
            "identity_only_s": decode_s + baseline_s,
            "full_selector_s": decode_s + full_s,
            "overhead_ratio": (decode_s + full_s) / (decode_s + baseline_s)}


def runtime_worker(arm, connection, index_path, split, codec_name, config):
    """Keep each arm in its own process so identity loads no model weights."""
    try:
        torch.set_num_threads(2)
        dataset = VideoClipDataset(index_path, split=split,
                                   num_frames=config["frames"],
                                   frame_size=config["frame_size"],
                                   temporal_stride=config["temporal_stride"],
                                   train=False, return_metadata=True)
        codec = StandardCodec(codec_name, preset=config["preset"],
                              strict_decode=True)
        analyzers = None
        risk = policy = None
        if arm == "full":
            risk, _frozen, policy = load_frozen(codec_name, config)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            analyzers = {model: ActionRecognitionAnalyzer(model, clip_size=112)
                         .freeze().to(device) for model in MODELS}
        connection.send({"ready": True})
        while True:
            index = connection.recv()
            if index is None:
                break
            if arm == "full" and torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
            start = time.perf_counter()
            source, _label, meta = dataset[index]
            rgb = (source.permute(1, 2, 3, 0).numpy() * 255).round().astype(np.uint8)
            decode_s = time.perf_counter() - start
            if arm == "identity":
                encode_s = identity_pipeline(rgb, codec)
                record = {"sequence_id": meta["sequence_id"],
                          "decode_s": decode_s,
                          "elapsed_s": decode_s + encode_s,
                          "codec_calls": len(QPS)}
            else:
                full_s, variants_s, clean_s, qps = full_pipeline(
                    source, rgb, analyzers, codec, risk, policy)
                record = {"sequence_id": meta["sequence_id"],
                          "decode_s": decode_s,
                          "elapsed_s": decode_s + full_s,
                          "codec_calls": len(QPS) * len(CANDIDATES),
                          "candidate_generation_s": variants_s,
                          "clean_analyzers_s": clean_s, "qps": qps,
                          "peak_gpu_reserved_bytes":
                          int(torch.cuda.max_memory_reserved())
                          if torch.cuda.is_available() else None}
            connection.send(record)
    except Exception as error:
        try:
            connection.send({"error": f"{type(error).__name__}: {error}"})
        except (BrokenPipeError, EOFError):
            pass
    finally:
        connection.close()


def process_tree_rss(process):
    """Current RSS of one arm plus its FFmpeg children (bytes)."""
    import psutil

    total = 0
    for member in [process, *process.children(recursive=True)]:
        try:
            total += member.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total


def request_measurement(connection, worker, index, interval_s=0.005):
    """Sample process-tree RSS throughout one arm; peak is a sampled bound."""
    import psutil

    process = psutil.Process(worker.pid)
    peak = process_tree_rss(process)
    connection.send(index)
    while not connection.poll(interval_s):
        if not worker.is_alive():
            raise RuntimeError(f"runtime worker exited with code {worker.exitcode}")
        peak = max(peak, process_tree_rss(process))
    peak = max(peak, process_tree_rss(process))
    record = connection.recv()
    if "error" in record:
        raise RuntimeError(record["error"])
    record["peak_process_tree_rss_bytes"] = peak
    return record


def summarize(rows):
    if not rows:
        raise ValueError("no timing records")
    result = {"n": len(rows), "unit": "one 16-frame source clip at all five QPs",
              "scope": "separate identity/full worker processes; paired order-balanced "
                       "wall time excludes model startup/download; full arm "
                       "includes all FFmpeg launches and encoder analyzers; "
                       "sampled process-tree RSS includes resident model weights"}
    for key in ("identity_only_s", "full_selector_s", "overhead_ratio"):
        values = np.asarray([r[key] for r in rows], dtype=np.float64)
        result[key] = {"median": float(np.median(values)),
                       "mean": float(np.mean(values)),
                       "p95": float(np.percentile(values, 95))}
    if "identity_peak_process_tree_rss_bytes" in rows[0]:
        for key in ("identity_peak_process_tree_rss_bytes",
                    "full_peak_process_tree_rss_bytes", "memory_overhead_ratio"):
            values = np.asarray([r[key] for r in rows], dtype=np.float64)
            result[key] = {"median": float(np.median(values)),
                           "mean": float(np.mean(values)),
                           "p95": float(np.percentile(values, 95))}
        result["peak_rss_sampling_interval_ms"] = 5
    result["identity_codec_calls_per_clip"] = len(QPS)
    result["full_codec_calls_per_clip"] = len(QPS) * len(CANDIDATES)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--codec", choices=("h264", "h265"), required=True)
    parser.add_argument("--split", choices=("train", "val"), default="val")
    parser.add_argument("--clips", type=int, default=20)
    parser.add_argument("--sample-ids", type=Path,
                        help="optional fixed JSON list of source clip IDs")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if not ffmpeg_available() or args.clips < 1:
        raise ValueError("ffmpeg/ffprobe and positive clip count required")
    try:
        import psutil
    except ImportError as error:
        raise RuntimeError("psutil is required for process-tree peak memory") from error
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    risk, frozen, policy = load_frozen(args.codec, config)
    dataset = VideoClipDataset(args.index, split=args.split,
                               num_frames=config["frames"],
                               frame_size=config["frame_size"],
                               temporal_stride=config["temporal_stride"],
                               train=False, return_metadata=True)
    if args.sample_ids is None:
        indices = balanced_indices(dataset.samples, args.clips,
                                   "paper-runtime-v1-20260924")
    else:
        ids = json.loads(args.sample_ids.read_text(encoding="utf-8"))
        if (not isinstance(ids, list) or len(ids) != args.clips
                or len(set(ids)) != len(ids)):
            raise ValueError("sample-ids must list exactly the requested clips")
        by_id = {clip_id(row): i for i, row in enumerate(dataset.samples)}
        if len(by_id) != len(dataset.samples) or any(key not in by_id for key in ids):
            raise ValueError("sample-ids missing from or duplicated in index")
        indices = [by_id[key] for key in ids]
    if len(indices) != args.clips:
        raise ValueError("not enough source clips")
    sample_ids = [clip_id(dataset.samples[i]) for i in indices]
    code_commit = subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", "rev-parse", "HEAD"],
        cwd=REPO, text=True).strip()
    manifest = {"experiment": "dual_v2_full_runtime", "codec": args.codec,
                "split": args.split, "clips": args.clips, "sample_ids": sample_ids,
                "sample_fingerprint": hashlib.sha256(
                    "\n".join(sorted(sample_ids)).encode()).hexdigest(),
                "sample_ids_sha256": hashlib.sha256(args.sample_ids.read_bytes()).hexdigest()
                if args.sample_ids else None,
                "index_sha256": hashlib.sha256(args.index.read_bytes()).hexdigest(),
                "config_sha256_lf": hashlib.sha256(CONFIG.read_bytes().replace(
                    b"\r\n", b"\n")).hexdigest(),
                "code_commit": code_commit,
                "frozen_policy_sha256": digest(frozen), "risk_sha256": digest(risk),
                "policy": policy, "qps": list(QPS), "candidates": list(CANDIDATES),
                "models": list(MODELS),
                "versions": {"python": platform.python_version(),
                              "torch": torch.__version__,
                              "torchvision": torchvision.__version__,
                              "psutil": psutil.__version__,
                              "ffmpeg": subprocess.check_output(
                                  ["ffmpeg", "-version"], text=True).splitlines()[0]},
                "hardware": {"cpu": platform.processor(),
                             "logical_cpus": os.cpu_count(),
                             "ram_bytes": psutil.virtual_memory().total,
                             "gpu": torch.cuda.get_device_name(0)
                             if torch.cuda.is_available() else None},
                "threading": {"torch_num_threads": torch.get_num_threads(),
                              "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
                              "OPENBLAS_NUM_THREADS":
                              os.environ.get("OPENBLAS_NUM_THREADS")},
                "memory_method": "5-ms sampled RSS of each worker plus its "
                                 "FFmpeg children; sampled peak is a lower bound",
                "comparison": "identity: five encode/decode calls, no analyzer; "
                              "full: 30 encode/decode calls plus two frozen "
                              "analyzers and policy selection"}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("output cache belongs to a different runtime run")
    write_json(manifest_path, manifest)
    context = mp.get_context("spawn")
    workers = {}
    try:
        for arm in ("identity", "full"):
            parent, child = context.Pipe()
            worker = context.Process(target=runtime_worker,
                args=(arm, child, args.index, args.split, args.codec, config),
                name=f"paper-runtime-{arm}")
            worker.start()
            child.close()
            workers[arm] = (parent, worker)
        for arm, (connection, worker) in workers.items():
            if not connection.poll(300):
                raise RuntimeError(f"{arm} worker did not initialize")
            ready = connection.recv()
            if ready != {"ready": True}:
                raise RuntimeError(f"{arm} worker initialization failed: {ready}")
        rows = []
        for number, index in enumerate(indices, 1):
            path = args.out_dir / "cache" / f"clip_{number:04d}.json"
            if path.exists():
                row = json.loads(path.read_text(encoding="utf-8"))
            else:
                reverse = int(hashlib.sha256(
                    f"paper-runtime-order-20260924\0{sample_ids[number-1]}".encode()
                ).hexdigest(), 16) % 2 == 1
                order = ("full", "identity") if reverse else ("identity", "full")
                measurements = {arm: request_measurement(*workers[arm], index)
                                for arm in order}
                identity = measurements["identity"]
                full = measurements["full"]
                if (identity["sequence_id"] != sample_ids[number-1]
                        or full["sequence_id"] != sample_ids[number-1]
                        or identity["codec_calls"] != len(QPS)
                        or full["codec_calls"] != len(QPS) * len(CANDIDATES)):
                    raise ValueError("runtime worker clip or codec-call mismatch")
                row = {"sequence_id": sample_ids[number-1],
                       "arm_order": list(order), "qps": full["qps"],
                       "identity_only_s": identity["elapsed_s"],
                       "full_selector_s": full["elapsed_s"],
                       "overhead_ratio": full["elapsed_s"] / identity["elapsed_s"],
                       "identity_peak_process_tree_rss_bytes":
                           identity["peak_process_tree_rss_bytes"],
                       "full_peak_process_tree_rss_bytes":
                           full["peak_process_tree_rss_bytes"],
                       "memory_overhead_ratio":
                           full["peak_process_tree_rss_bytes"] /
                           identity["peak_process_tree_rss_bytes"],
                       "full_peak_gpu_reserved_bytes": full["peak_gpu_reserved_bytes"],
                       "identity_codec_calls": identity["codec_calls"],
                       "full_codec_calls": full["codec_calls"],
                       "identity_decode_s": identity["decode_s"],
                       "full_decode_s": full["decode_s"],
                       "candidate_generation_s": full["candidate_generation_s"],
                       "clean_analyzers_s": full["clean_analyzers_s"]}
                write_json(path, row)
            if (row["sequence_id"] != sample_ids[number-1]
                    or row["identity_codec_calls"] != len(QPS)
                    or row["full_codec_calls"] != len(QPS) * len(CANDIDATES)):
                raise ValueError("stale or incomplete runtime cache")
            rows.append(row)
            print(f"[runtime] {args.codec} {number}/{len(indices)}", flush=True)
    finally:
        for connection, worker in workers.values():
            if worker.is_alive():
                try:
                    connection.send(None)
                except (BrokenPipeError, EOFError):
                    pass
                worker.join(timeout=10)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=10)
            connection.close()
    result_path = args.out_dir / "runtime_result.json"
    report = {"manifest": manifest, "summary": summarize(rows), "records": rows}
    write_json(result_path, report)
    (args.out_dir / "runtime_result.sha256").write_text(
        hashlib.sha256(result_path.read_bytes()).hexdigest() + "  runtime_result.json\n",
        encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
