"""Audited V11 CAL proxy extraction and locked primary-analyzer selection."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import time

import cv2
import numpy as np
import torch

from ops.dual_codec_search import FIELDS, digest, metrics
from ops.v10_spatial_gate import historical_stage, read_clip
from ops.v7_pixel_proxy import find_planned_videos, sha256
from ops.v11_spatial_policy import QPS, QP_SETS, choose, distance, grid
from src.codecs.standard import StandardCodec, ffmpeg_available
from src.models.codec_search import CANDIDATES, make_candidates, normalized_bpp

REPO = Path(__file__).resolve().parents[1]
PREREG = "docs/PREREGISTRATION_V11_112_RESIDUAL.md"
PLAN = "configs/v10_spatial_plan.json"
INPUT = "configs/v10_spatial/calibration_input.json"
RESULT = "configs/v11_spatial/frozen_calibration.json"
PLAN_SHA = "bb4b9aa245ff2d8b5f92cb1a45dedb65adfc8a664543878bb7b9cdb1486b421e"
INPUT_SHA = "db9fd6eef315657b33f9e0d557260c7af2a89857633193e6d41c83b056a7983d"
PRIMARY = ("r2plus1d_18", "r3d_18")
SHARDS = 4
SEED, DRAWS = 20261008, 2000


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-c", f"safe.directory={REPO.as_posix()}", *args], cwd=REPO)


def hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def committed(relative: str, ref: str = "HEAD") -> bytes:
    blob = git("show", f"{ref}:{relative}")
    checkout = (REPO / relative).read_bytes()
    if checkout != blob and checkout.replace(b"\r\n", b"\n") != blob:
        raise ValueError(f"working file differs from committed artifact: {relative}")
    return blob


def protocol(prereg_commit: str) -> tuple[dict, dict, dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", prereg_commit):
        raise ValueError("full 40-character preregistration commit required")
    git("merge-base", "--is-ancestor", prereg_commit, "HEAD")
    prereg = committed(PREREG, prereg_commit)
    if b"\nPREREGISTRATION_LOCKED: true\n" not in prereg or committed(PREREG) != prereg:
        raise ValueError("V11 protocol not locked at supplied commit")
    plan_blob, input_blob = committed(PLAN), committed(INPUT)
    if hash_bytes(plan_blob) != PLAN_SHA or hash_bytes(input_blob) != INPUT_SHA:
        raise ValueError("source plan or CAL input differs from preregistration")
    for rel in ("ops/v11_spatial_policy.py", "ops/v11_spatial_cal.py", "kaggle/v11_spatial_cal_cell.sh"):
        committed(rel)
    git("diff", "--exit-code", "HEAD", "--", "ops", "src", "kaggle/v11_spatial_cal_cell.sh")
    plan, data = json.loads(plan_blob), json.loads(input_blob)
    expected = plan["stages"]["calibration"]
    sources = data["sources"]
    ids = [s["sequence_id"] for s in sources]
    if (data.get("stage") != "calibration" or len(sources) != len(expected) != 200
            or any({k: source[k] for k in ("sequence_id", "source_sha256")} != locked
                   for source, locked in zip(sources, expected, strict=True))
            or digest(ids) != plan["source_fingerprints"]["calibration"]
            or len(set(Path(s).stem for s in ids)) != 200
            or len(set(s["source_sha256"] for s in sources)) != 200):
        raise ValueError("CAL cohort changed or overlaps")
    for source in sources:
        if [m["qp"] for m in source["measurements"]] != list(QPS):
            raise ValueError("QP schedule changed")
        for fixed in source["measurements"]:
            if (fixed["v2"] not in CANDIDATES or fixed["v6"] not in CANDIDATES
                    or set(fixed["bpp"]) != set(CANDIDATES)
                    or any(not math.isfinite(v) or v <= 0 for v in fixed["bpp"].values())):
                raise ValueError("invalid frozen choice or bitrate")
    code_hash = hash_bytes(git("ls-tree", "-r", "HEAD", "--", "ops", "src", "kaggle/v11_spatial_cal_cell.sh"))
    context = {"experiment": "v11_h265_analyzer_grid_cal", "code_commit": git("rev-parse", "HEAD").decode().strip(),
               "code_fingerprint": code_hash, "preregistration_commit": prereg_commit,
               "preregistration_sha256": hash_bytes(prereg), "source_plan_sha256": PLAN_SHA,
               "input_sha256": INPUT_SHA, "source_fingerprint": plan["source_fingerprints"]["calibration"],
               "bootstrap_seed_if_dev": SEED, "bootstrap_draws_if_dev": DRAWS,
               "bootstrap_unit_if_dev": "source video; QPs, arms, analyzers paired",
               "scope": "reused CAL development; no holdout"}
    return plan, data, context


def write_json(path: Path, value: dict) -> None:
    if path.exists() or path.with_suffix(".sha256").exists():
        raise ValueError(f"fresh artifact required: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    path.write_bytes(body)
    path.with_suffix(".sha256").write_text(f"{hash_bytes(body)}  {path.name}\n", encoding="ascii")


def rows_bytes(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows).encode()


def measured_names(fixed: dict) -> set[str]:
    return {"identity128", fixed["v2"], fixed["v6"]}


def measure_source(source: dict, path: Path, codec: StandardCodec) -> tuple[dict, int]:
    if sha256(path) != source["source_sha256"]:
        raise ValueError("source byte hash mismatch")
    clip = read_clip(path)
    candidates = make_candidates(clip)
    measurements, trials = [], 0
    for fixed in source["measurements"]:
        qp, observed = fixed["qp"], {}
        for name in sorted(measured_names(fixed)):
            candidate = candidates[name]
            _, height, width, _ = candidate.shape
            start = time.perf_counter()
            decoded, native_bpp = codec._encode_decode_clip(candidate, qp=qp)
            elapsed = time.perf_counter() - start
            bpp = normalized_bpp(native_bpp, height, width)
            if abs(bpp - fixed["bpp"][name]) > 1e-9:
                raise ValueError(f"re-encoded bpp mismatch: {source['sequence_id']} {qp} {name}")
            coded_bytes = int(round(bpp * 16 * 128 * 128 / 8))
            observed[name] = {"bpp": bpp, "coded_bytes": coded_bytes,
                              "d112": distance(clip, decoded), "encode_decode_s": elapsed,
                              "decoded_sha256": hash_bytes(decoded.tobytes())}
            trials += 1
        measurements.append({"qp": qp, "candidates": observed})
    return {"sequence_id": source["sequence_id"], "source_sha256": source["source_sha256"],
            "measurements": measurements}, trials


def run_shard(source_root: Path, shard: int, out: Path, data: dict, context: dict) -> dict:
    if shard not in range(SHARDS) or out.exists() or not source_root.is_dir() or not ffmpeg_available():
        raise ValueError("invalid shard/source root/FFmpeg or nonfresh output")
    sources = data["sources"][shard::SHARDS]
    paths = find_planned_videos(source_root, [s["sequence_id"] for s in sources])
    for source in sources:
        if sha256(paths[source["sequence_id"]]) != source["source_sha256"]:
            raise ValueError("source hash mismatch before measurement")
    out.mkdir(parents=True)
    torch.set_num_threads(2)
    codec = StandardCodec("h265", preset="medium", strict_decode=True)
    rows, count = [], 0
    for index, source in enumerate(sources):
        row, trials = measure_source(source, paths[source["sequence_id"]], codec)
        rows.append(row)
        count += trials
        print(f"[V11 CAL] shard={shard} {index+1}/{len(sources)} trials={count}", flush=True)
    record = out / "shard_records.jsonl"
    record.write_bytes(rows_bytes(rows))
    manifest = {"kind": "v11_cal_shard", "provenance": context, "shard": shard, "shards": SHARDS,
                "n": len(rows), "source_ids": [s["sequence_id"] for s in sources],
                "records_sha256": sha256(record), "trial_encode_decode_count": count,
                "versions": {"python": platform.python_version(), "torch": torch.__version__,
                             "opencv": cv2.__version__, "numpy": np.__version__,
                             "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0]},
                "device": "cpu; no analyzer or labels"}
    write_json(out / "manifest.json", manifest)
    return manifest


def _finite(v) -> bool:
    return type(v) in (float, int) and math.isfinite(v)


def load_shards(folders: list[Path], data: dict, context: dict) -> tuple[list[dict], list[dict]]:
    if len(folders) != SHARDS:
        raise ValueError("exactly four shard folders required")
    seen, by_id, manifests, commits = set(), {}, [], set()
    for folder in folders:
        manifest_path, records_path = folder / "manifest.json", folder / "shard_records.jsonl"
        sidecar = folder / "manifest.sha256"
        if sidecar.read_text(encoding="ascii").split() != [sha256(manifest_path), "manifest.json"]:
            raise ValueError("manifest SHA-256 sidecar mismatch")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shard = manifest.get("shard")
        if type(shard) is not int or shard not in range(SHARDS) or shard in seen:
            raise ValueError("duplicate or invalid shard")
        sources = data["sources"][shard::SHARDS]
        provenance = manifest.get("provenance", {})
        if (manifest.get("kind") != "v11_cal_shard" or manifest.get("shards") != SHARDS
                or manifest.get("n") != len(sources)
                or manifest.get("source_ids") != [s["sequence_id"] for s in sources]
                or manifest.get("records_sha256") != sha256(records_path)
                or any(provenance.get(k) != v for k, v in context.items() if k != "code_commit")
                or manifest.get("device") != "cpu; no analyzer or labels"):
            raise ValueError("shard manifest/hash/provenance mismatch")
        worker_commit = provenance.get("code_commit", "")
        if not re.fullmatch(r"[0-9a-f]{40}", worker_commit):
            raise ValueError("invalid worker commit")
        git("merge-base", "--is-ancestor", worker_commit, "HEAD")
        commits.add(worker_commit)
        rows = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
        expected_count = sum(len(measured_names(fixed)) for source in sources for fixed in source["measurements"])
        if len(rows) != len(sources) or manifest.get("trial_encode_decode_count") != expected_count:
            raise ValueError("incomplete records or trial count")
        for row, source in zip(rows, sources, strict=True):
            if (set(row) != {"sequence_id", "source_sha256", "measurements"}
                    or row["sequence_id"] != source["sequence_id"]
                    or row["source_sha256"] != source["source_sha256"]
                    or row["sequence_id"] in by_id
                    or [m.get("qp") for m in row["measurements"]] != list(QPS)):
                raise ValueError("record source, schema or QP mismatch")
            for observed, fixed in zip(row["measurements"], source["measurements"], strict=True):
                if set(observed) != {"qp", "candidates"} or set(observed["candidates"]) != measured_names(fixed):
                    raise ValueError("candidate record incomplete or contaminated")
                for name, measured in observed["candidates"].items():
                    if (set(measured) != {"bpp", "coded_bytes", "d112", "encode_decode_s", "decoded_sha256"}
                            or not _finite(measured["bpp"])
                            or abs(measured["bpp"] - fixed["bpp"][name]) > 1e-9
                            or type(measured["coded_bytes"]) is not int or measured["coded_bytes"] <= 0
                            or abs(measured["coded_bytes"] * 8 / (16 * 128 * 128) - measured["bpp"]) > 1e-9
                            or not _finite(measured["d112"]) or not 0 <= measured["d112"] <= 2
                            or not _finite(measured["encode_decode_s"]) or measured["encode_decode_s"] < 0
                            or not re.fullmatch(r"[0-9a-f]{64}", measured["decoded_sha256"])):
                        raise ValueError("invalid measured rate, proxy or hash")
            by_id[row["sequence_id"]] = row
        seen.add(shard)
        manifests.append({**manifest, "manifest_sha256": sha256(manifest_path)})
    if seen != set(range(SHARDS)) or len(by_id) != 200 or len(commits) != 1:
        raise ValueError("mixed revisions or incomplete cohort")
    return [by_id[s["sequence_id"]] for s in data["sources"]], sorted(manifests, key=lambda m: m["shard"])


def selected_arrays(historical: list, pixels: list, sources: list, policy: dict | None):
    values, distances, switches = [], [], Counter()
    for old, pixel, source in zip(historical, pixels, sources, strict=True):
        video = []
        for measurement, proxy, fixed in zip(old["measurements"], pixel["measurements"], source["measurements"], strict=True):
            name = fixed["v6"] if policy is None else choose(measurement["qp"], fixed,
                        {k: {"bpp": v["bpp"], "d112": v["d112"]} for k, v in proxy["candidates"].items()}, policy)[0]
            candidate = next(c for c in measurement["candidates"] if c["name"] == name)
            video.append([float(candidate["bpp"]), *[float(candidate[f]) for f in FIELDS]])
            distances.append(proxy["candidates"][name]["d112"])
            if name != fixed["v6"]:
                switches[str(measurement["qp"])] += 1
        values.append(video)
    return np.asarray(values, dtype=np.float64), float(np.mean(distances)), dict(switches)


def feasible(report: dict, baseline: dict, improvement: float) -> bool:
    if improvement <= 1e-6:
        return False
    for model in PRIMARY:
        m, base = report[model]["metrics"], baseline[model]["metrics"]
        if (not all(_finite(m.get(k)) for k in ("bd_rate_top1_pct", "bd_accuracy_top1", "min_same_qp_top1_gap"))
                or not _finite(base.get("bd_rate_top1_pct"))
                or m["bd_rate_top1_pct"] >= -10
                or m["bd_rate_top1_pct"] > base["bd_rate_top1_pct"] + 1.0
                or m["bd_accuracy_top1"] <= 0 or m["min_same_qp_top1_gap"] < -0.01 - 1e-12):
            return False
    return True


def rank_key(row: dict) -> tuple:
    p = row["policy"]
    rates = [row["analyzers"][m]["metrics"]["bd_rate_top1_pct"] for m in PRIMARY]
    return (-row["mean_d112_reduction"], max(rates), sum(rates), row["switch_count"],
            p["tau"], p["slack"], list(QP_SETS).index(p["qp_mode"]))


def calibrate(folders: list[Path], cache_root: Path, data: dict, context: dict) -> dict:
    out = REPO / RESULT
    if out.exists():
        raise ValueError("CAL result exists; repeated selection prohibited")
    pixels, manifests = load_shards(folders, data, context)
    old, _, _ = historical_stage(cache_root, "calibration")
    if [r["sequence_id"] for r in old] != [r["sequence_id"] for r in pixels]:
        raise ValueError("historical correctness/proxy source mismatch")
    identity = []
    for row in old:
        video = []
        for measurement in row["measurements"]:
            candidate = next(c for c in measurement["candidates"] if c["name"] == "identity128")
            video.append([float(candidate["bpp"]), *[float(candidate[f]) for f in FIELDS]])
        identity.append(video)
    identity = np.asarray(identity, dtype=np.float64)
    baseline_values, baseline_distance, _ = selected_arrays(old, pixels, data["sources"], None)
    baseline_metrics = metrics(identity, baseline_values)
    rows = []
    for policy in grid():
        values, mean_distance, by_qp = selected_arrays(old, pixels, data["sources"], policy)
        report = metrics(identity, values)
        improvement = baseline_distance - mean_distance
        rows.append({"policy": policy, "analyzers": report, "mean_d112": mean_distance,
                     "mean_d112_reduction": improvement, "switch_count": sum(by_qp.values()),
                     "switches_by_qp": by_qp, "feasible": feasible(report, baseline_metrics, improvement)})
    candidates = [row for row in rows if row["feasible"]]
    chosen = min(candidates, key=rank_key) if candidates else None
    result = {"kind": "v11_calibration_result", "provenance": context, "n": len(old),
              "shard_manifests": manifests, "v6_baseline": {"analyzers": baseline_metrics,
              "mean_d112": baseline_distance}, "grid": rows,
              "selected_policy": chosen["policy"] if chosen else None,
              "status": "FREEZE_BEFORE_DEV" if chosen else "NO_GO_STOP_BEFORE_DEV",
              "mc3_18": "CHƯA ĐO; excluded from CAL", "dev": "CHƯA ĐO", "holdout": "CHƯA ĐO"}
    write_json(out, result)
    return {"path": str(out), "sha256": sha256(out), "status": result["status"],
            "selected_policy": result["selected_policy"], "feasible_count": len(candidates)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg-commit", required=True)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("preflight")
    shard = actions.add_parser("shard")
    shard.add_argument("--source-root", type=Path, required=True)
    shard.add_argument("--shard", type=int, choices=range(SHARDS), required=True)
    shard.add_argument("--out-dir", type=Path, required=True)
    cal = actions.add_parser("calibrate")
    cal.add_argument("--shard-dir", type=Path, action="append", required=True)
    cal.add_argument("--cache-root", type=Path, required=True)
    args = parser.parse_args()
    _, data, context = protocol(args.prereg_commit)
    if args.action == "preflight":
        output = context
    elif args.action == "shard":
        output = run_shard(args.source_root, args.shard, args.out_dir, data, context)
    else:
        output = calibrate(args.shard_dir, args.cache_root, data, context)
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
