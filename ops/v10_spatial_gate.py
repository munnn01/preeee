"""Audited CAL search and frozen DEV assessment for V10; no TEST/holdout command."""
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
import tempfile
import time

import cv2
import numpy as np

from ops.codec_search_ar import as_video
from ops.dual_codec_search import FIELDS, digest, metrics
from ops.v5_dev_agreement import load_locked_dev_cache
from ops.v6_dev_residual import predicted_measurements, select_residual
from ops.v6_frozen import load_frozen_v6
from ops.v7_dev_transfer import load_cache_stage
from ops.v7_pixel_proxy import find_planned_videos, sha256
from ops.v8_motion_pilot import summarize
from ops.v10_spatial_policy import QPS, choose, policy_grid, validate_policy, spatial_proxy
from src.codecs.standard import StandardCodec, ffmpeg_available
from src.data.video_dataset import VideoClipDataset
from src.models.codec_search import CANDIDATES, make_candidates, normalized_bpp

REPO = Path(__file__).resolve().parents[1]
PREREG = "docs/PREREGISTRATION_V10_SPATIAL_GATE.md"
PLAN = "configs/v10_spatial_plan.json"
PLAN_SHA = "bb4b9aa245ff2d8b5f92cb1a45dedb65adfc8a664543878bb7b9cdb1486b421e"
INPUTS = {s: f"configs/v10_spatial/{s}_input.json" for s in ("calibration", "dev")}
FROZEN = "configs/v10_spatial/frozen_calibration.json"
EXPERIMENT = "v10_spatial_gate_h265"
PRIMARY = ("r2plus1d_18", "r3d_18")
MODELS = (*PRIMARY, "mc3_18")
ARMS = ("identity", "area112", "v2", "v6", "v10")
SEED, DRAWS, SHARDS = 20261007, 2000, 4
UNIT = "source video; all QPs, arms and analyzers paired"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-c", f"safe.directory={REPO.as_posix()}", *args], cwd=REPO)


def hash_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def committed(relative: str, ref: str = "HEAD") -> bytes:
    raw = (REPO / relative).read_bytes()
    blob = git("show", f"{ref}:{relative}")
    if raw != blob and raw.replace(b"\r\n", b"\n") != blob:
        raise ValueError(f"working file differs from committed artifact: {relative}")
    return blob


def protocol(prereg_commit: str) -> tuple[dict, dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", prereg_commit):
        raise ValueError("full lowercase preregistration commit required")
    git("merge-base", "--is-ancestor", prereg_commit, "HEAD")
    prereg = committed(PREREG, prereg_commit)
    if b"\nPREREGISTRATION_LOCKED: true\n" not in prereg:
        raise ValueError("V10 preregistration is a draft; lock and commit before running")
    blob = committed(PLAN, prereg_commit)
    if hash_bytes(blob) != PLAN_SHA:
        raise ValueError("V10 source plan changed")
    plan = json.loads(blob)
    for rel, expected in plan["input_sha256"].items():
        if hash_bytes(committed(rel)) != expected:
            raise ValueError(f"historical input changed: {rel}")
    seen_ids, seen_hashes = set(), set()
    for stage in INPUTS:
        sources = plan["stages"][stage]
        ids = [s["sequence_id"] for s in sources]
        hashes = [s["source_sha256"] for s in sources]
        stems = [Path(key).stem for key in ids]
        if (len(ids) != 200 or len(set(stems)) != 200 or len(set(hashes)) != 200
                or set(stems) & seen_ids or set(hashes) & seen_hashes
                or digest(ids) != plan["source_fingerprints"][stage]
                or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes)):
            raise ValueError("invalid or overlapping CAL/DEV source plan")
        seen_ids.update(stems)
        seen_hashes.update(hashes)
    for rel in ("ops/v10_spatial_policy.py", "ops/v10_spatial_gate.py", "kaggle/v10_spatial_gate_cell.sh"):
        committed(rel)
    git("diff", "--exit-code", "HEAD", "--", "ops", "src", "kaggle/v10_spatial_gate_cell.sh")
    code_hash = hash_bytes(git("ls-tree", "-r", "HEAD", "--", "ops", "src", "kaggle/v10_spatial_gate_cell.sh"))
    return plan, {"experiment": EXPERIMENT, "code_commit": git("rev-parse", "HEAD").decode().strip(),
                  "code_fingerprint": code_hash, "preregistration_commit": prereg_commit,
                  "preregistration_sha256": hash_bytes(prereg), "source_plan_sha256": PLAN_SHA,
                  "bootstrap_seed": SEED, "bootstrap_draws": DRAWS, "bootstrap_unit": UNIT,
                  "scope": "reused CAL/DEV development; no holdout"}


def matches_context(meta: dict, context: dict) -> bool:
    return all(meta.get(k) == v for k, v in context.items() if k != "code_commit")


def write_json(path: Path, value: dict) -> None:
    if path.exists() or path.with_suffix(".sha256").exists():
        raise ValueError(f"fresh artifact required: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode())
    path.with_suffix(".sha256").write_bytes(f"{sha256(path)}  {path.name}\n".encode("ascii"))


def rank_key(row: dict) -> tuple:
    p = row["policy"]
    return (row["mean_spatial_excess"], row["worst_primary_bd_rate"], row["sum_primary_bd_rate"],
            p["complexity_quantile"], p["tau"], p["minimum_saving"], p["spatial_weight"])


def load_freeze(context: dict) -> tuple[dict, str]:
    raw = committed(FROZEN)
    freeze = json.loads(raw)
    if (freeze.get("kind") != "calibration_result" or not matches_context(freeze.get("provenance", {}), context)
            or freeze.get("n") != 200 or len(freeze.get("grid", [])) != 81):
        raise ValueError("invalid committed CAL result")
    for row in freeze["grid"]:
        validate_policy(row["policy"])
        if set(row["analyzers"]) != set(PRIMARY) or row["feasible"] != primary_feasible(row["analyzers"]):
            raise ValueError("CAL feasibility changed or transfer analyzer entered selection")
    tuples = {(x["policy"]["complexity_quantile"], x["policy"]["tau"],
               x["policy"]["minimum_saving"], x["policy"]["spatial_weight"]) for x in freeze["grid"]}
    if len(tuples) != 81:
        raise ValueError("CAL grid is incomplete or duplicated")
    feasible = [x for x in freeze["grid"] if x["feasible"]]
    chosen = min(feasible, key=rank_key) if feasible else None
    if chosen is None or freeze.get("selected_policy") != chosen["policy"]:
        raise ValueError("CAL NO-GO or manually changed selected policy; DEV prohibited")
    validate_policy(chosen["policy"])
    if freeze.get("input_sha256") != hash_bytes(committed(INPUTS["calibration"])):
        raise ValueError("CAL input changed after freeze")
    return freeze, hash_bytes(raw)


def historical_stage(cache_root: Path, stage: str):
    lock, _ = load_locked_dev_cache()
    old_plan = json.loads(committed("configs/v7_dev_proxy_plan.json"))
    return load_cache_stage(cache_root, stage, old_plan, lock)


def prepare_inputs(cache_root: Path, stage: str, plan: dict, context: dict) -> dict:
    if stage not in INPUTS:
        raise ValueError("only CAL/DEV stages are allowed")
    freeze, freeze_sha = load_freeze(context) if stage == "dev" else (None, None)
    out = REPO / INPUTS[stage]
    if out.exists():
        raise ValueError("input manifest already exists")
    rows, risk, v2_policy = historical_stage(cache_root, stage)
    v6_policy, models = load_frozen_v6()
    prepared = predicted_measurements(rows, risk, v2_policy, models)
    sources = []
    for expected, row, video in zip(plan["stages"][stage], rows, prepared, strict=True):
        if expected["sequence_id"] != row["sequence_id"]:
            raise ValueError("cache/source order mismatch")
        choices = []
        for measurement, obs, base, probabilities in video:
            residual = select_residual(obs, base, probabilities, v6_policy)
            choices.append({"qp": measurement["qp"], "v2": CANDIDATES[base], "v6": CANDIDATES[residual],
                            "bpp": {c["name"]: float(c["bpp"]) for c in measurement["candidates"]}})
        sources.append({**expected, "measurements": choices})
    data = {"kind": "inputs", "provenance": context, "stage": stage, "sources": sources,
            "source_fingerprint": plan["source_fingerprints"][stage], "qps": list(QPS),
            "candidates": list(CANDIDATES), "calibration_sha256": freeze_sha,
            "policy": freeze["selected_policy"] if freeze else None}
    write_json(out, data)
    return {"path": str(out), "sha256": sha256(out), "next": "commit this manifest before shard execution"}


def load_inputs(stage: str, plan: dict, context: dict) -> tuple[dict, str]:
    if stage not in INPUTS:
        raise ValueError("unsupported stage")
    raw = committed(INPUTS[stage])
    data = json.loads(raw)
    if (data.get("kind") != "inputs" or data.get("stage") != stage
            or not matches_context(data.get("provenance", {}), context)
            or data.get("qps") != list(QPS) or data.get("candidates") != list(CANDIDATES)
            or data.get("source_fingerprint") != plan["source_fingerprints"][stage]
            or len(data.get("sources", [])) != 200):
        raise ValueError("input manifest not from locked V10 preparation")
    for source, expected in zip(data["sources"], plan["stages"][stage], strict=True):
        if (set(source) != {"sequence_id", "source_sha256", "measurements"}
                or any(source.get(k) != v for k, v in expected.items())
                or [m.get("qp") for m in source["measurements"]] != list(QPS)):
            raise ValueError("source or QP manifest mismatch")
        for m in source["measurements"]:
            if (set(m) != {"qp", "v2", "v6", "bpp"} or m["v2"] not in CANDIDATES
                    or m["v6"] not in CANDIDATES or set(m["bpp"]) != set(CANDIDATES)
                    or any(not finite(v) or v <= 0 for v in m["bpp"].values())):
                raise ValueError("input manifest contains invalid rates, choices or unexpected fields")
    if stage == "dev":
        frozen, frozen_sha = load_freeze(context)
        if data.get("calibration_sha256") != frozen_sha or data.get("policy") != frozen["selected_policy"]:
            raise ValueError("DEV input not bound to frozen CAL choice")
    elif data.get("policy") is not None or data.get("calibration_sha256") is not None:
        raise ValueError("CAL input must not have a selected policy")
    return data, hash_bytes(raw)


def finite(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def gate_view(candidates: dict) -> dict:
    return {name: {k: row[k] for k in ("bpp", "spatial_error")} for name, row in candidates.items()}


def decisions(row: dict, source: dict, policy: dict) -> list[dict]:
    result = []
    for m, fixed in zip(row["measurements"], source["measurements"], strict=True):
        name, reason = choose(m["qp"], row["complexity"], gate_view(m["candidates"]),
                              fixed["v2"], fixed["v6"], policy)
        result.append({"identity": "identity128", "area112": "area112",
                       "v2": fixed["v2"], "v6": fixed["v6"], "v10": name, "reason": reason})
    return result


def read_clip(path: Path) -> np.ndarray:
    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    if not ok:
        raise ValueError("undecodable source; no replacement permitted")
    dataset = VideoClipDataset.__new__(VideoClipDataset)
    dataset.num_frames, dataset.frame_size = 16, 128
    dataset.temporal_stride, dataset.train = 2, False
    return dataset._read_clip(str(path))


def measure_pixels(source: dict, path: Path, codec) -> tuple[dict, dict]:
    if sha256(path) != source["source_sha256"]:
        raise ValueError("source byte hash mismatch")
    clip = read_clip(path)
    variants = make_candidates(clip)
    complexity = spatial_proxy(clip, clip)["complexity"]
    measurements, decoded = [], {}
    for fixed in source["measurements"]:
        qp, values = fixed["qp"], {}
        for name in CANDIDATES:
            candidate = variants[name]
            _, h, w, _ = candidate.shape
            start = time.perf_counter()
            reconstruction, native_bpp = codec._encode_decode_clip(candidate, qp=qp)
            elapsed = time.perf_counter() - start
            bpp = normalized_bpp(native_bpp, h, w)
            if abs(bpp - fixed["bpp"][name]) > 1e-9:
                raise ValueError(f"re-encoded bpp mismatch: {source['sequence_id']} {qp} {name}")
            proxy = spatial_proxy(clip, reconstruction)
            values[name] = {"bpp": bpp, "coded_bytes": int(round(bpp * 16 * 128 * 128 / 8)),
                            "spatial_error": proxy["spatial_error"], "encode_decode_s": elapsed,
                            "decoded_sha256": hash_bytes(reconstruction.tobytes())}
            decoded[(qp, name)] = reconstruction
        measurements.append({"qp": qp, "candidates": values})
    return {"sequence_id": source["sequence_id"], "source_sha256": source["source_sha256"],
            "complexity": complexity, "measurements": measurements}, decoded


def rows_bytes(rows: list[dict]) -> bytes:
    return "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows).encode()


def run_shard(root: Path, stage: str, shard: int, out: Path, plan: dict, context: dict) -> dict:
    if shard not in range(SHARDS) or out.exists() or not root.is_dir() or not ffmpeg_available():
        raise ValueError("invalid shard/source root/FFmpeg or nonfresh output")
    data, input_sha = load_inputs(stage, plan, context)
    assigned = data["sources"][shard::SHARDS]
    paths = find_planned_videos(root, [s["sequence_id"] for s in assigned])
    for source in assigned:
        if sha256(paths[source["sequence_id"]]) != source["source_sha256"]:
            raise ValueError("source hash mismatch before measurements")
    out.mkdir(parents=True)
    codec = StandardCodec("h265", preset="medium", strict_decode=True)
    rows = []
    versions = {"python": platform.python_version(), "opencv": cv2.__version__, "numpy": np.__version__,
                "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0]}
    device_name = "cpu; proxy extraction only"
    weight_hashes = {}
    with tempfile.TemporaryDirectory(prefix="v10_decoded_") as temp:
        spool = Path(temp)
        for number, source in enumerate(assigned):
            row, decoded = measure_pixels(source, paths[source["sequence_id"]], codec)
            if stage == "dev":
                for m, decision in zip(row["measurements"], decisions(row, source, data["policy"]), strict=True):
                    m["choices"] = decision
                    for name in set(decision[a] for a in ARMS):
                        np.save(spool / f"{number}_{m['qp']}_{name}.npy", decoded[(m["qp"], name)], allow_pickle=False)
            rows.append(row)
            print(f"[V10 proxy] {stage} shard={shard} {number + 1}/{len(assigned)}", flush=True)
        # Persist every decision before constructing any analyzer or reading a label.
        proxy_path = out / "proxy_records.jsonl"
        proxy_path.write_bytes(rows_bytes(rows))
        proxy_sha = sha256(proxy_path)
        if stage == "dev":
            import torch
            import torchvision
            from src.tasks.action_recognition import ActionRecognitionAnalyzer, _canon, kinetics_category_index, kinetics_categories
            if any(kinetics_categories(m) != kinetics_categories(MODELS[0]) for m in MODELS):
                raise ValueError("analyzer category order mismatch")
            categories = kinetics_category_index(MODELS[0])
            torch.manual_seed(53)
            torch.set_num_threads(2)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            models = {m: ActionRecognitionAnalyzer(m, clip_size=112).freeze().to(device) for m in MODELS}
            for model, analyzer in models.items():
                state_hash = hashlib.sha256()
                for name, tensor in sorted(analyzer.state_dict().items()):
                    tensor = tensor.detach().cpu().contiguous()
                    state_hash.update(f"{name}\t{tensor.dtype}\t{tuple(tensor.shape)}\n".encode())
                    state_hash.update(tensor.numpy().tobytes())
                weight_hashes[model] = state_hash.hexdigest()
            device_name = torch.cuda.get_device_name() if device.type == "cuda" else "cpu"
            versions.update(torch=torch.__version__, torchvision=torchvision.__version__)
            for number, row in enumerate(rows):
                label = categories[_canon(row["sequence_id"].split("/")[0])]
                row["label"] = label
                for measurement in row["measurements"]:
                    scored = {}
                    for name in sorted(set(measurement["choices"][a] for a in ARMS)):
                        reconstructed = np.load(spool / f"{number}_{measurement['qp']}_{name}.npy", allow_pickle=False)
                        if hash_bytes(reconstructed.tobytes()) != measurement["candidates"][name]["decoded_sha256"]:
                            raise ValueError("decoded stream changed after choices were recorded")
                        scores = {}
                        video = as_video(reconstructed).to(device)
                        for model, analyzer in models.items():
                            if device.type == "cuda":
                                torch.cuda.synchronize()
                            start = time.perf_counter()
                            with torch.no_grad():
                                prediction = int(analyzer.predict(video).argmax(1).item())
                            if device.type == "cuda":
                                torch.cuda.synchronize()
                            scores[model] = {"predicted_class_index": prediction, "correct": prediction == label,
                                             "inference_s": time.perf_counter() - start}
                        scored[name] = {"name": name, "bpp": measurement["candidates"][name]["bpp"], "analyzers": scores}
                    measurement["arms"] = {arm: scored[measurement["choices"][arm]] for arm in ARMS}
                print(f"[V10 score] shard={shard} {number + 1}/{len(rows)}", flush=True)
    records = out / "shard_records.jsonl"
    records.write_bytes(rows_bytes(rows))
    manifest = {"kind": "shard", "provenance": context, "stage": stage, "shard": shard, "shards": SHARDS,
                "n": len(rows), "source_ids": [s["sequence_id"] for s in assigned], "input_sha256": input_sha,
                "source_fingerprint": plan["source_fingerprints"][stage], "records_sha256": sha256(records),
                "proxy_records_sha256": proxy_sha, "trial_encode_decode_count": 30 * len(rows),
                "versions": versions, "device": device_name, "weight_state_sha256": weight_hashes,
                "calibration_sha256": data["calibration_sha256"]}
    write_json(out / "manifest.json", manifest)
    return manifest


def validate_record(row: dict, source: dict, stage: str, policy: dict | None) -> None:
    expected_keys = {"sequence_id", "source_sha256", "complexity", "measurements"}
    if stage == "dev":
        expected_keys.add("label")
    if (set(row) != expected_keys or row["sequence_id"] != source["sequence_id"]
            or row["source_sha256"] != source["source_sha256"]
            or not finite(row["complexity"]) or not 0 <= row["complexity"] <= 2
            or [m.get("qp") for m in row["measurements"]] != list(QPS)):
        raise ValueError("invalid source, forbidden fields or QP record")
    for m, fixed in zip(row["measurements"], source["measurements"], strict=True):
        keys = {"qp", "candidates"} | ({"choices", "arms"} if stage == "dev" else set())
        if set(m) != keys or set(m["candidates"]) != set(CANDIDATES):
            raise ValueError("incomplete/contaminated candidate record")
        for name, value in m["candidates"].items():
            if (set(value) != {"bpp", "spatial_error", "coded_bytes", "decoded_sha256", "encode_decode_s"}
                    or not finite(value["bpp"]) or abs(value["bpp"] - fixed["bpp"][name]) > 1e-9
                    or type(value["coded_bytes"]) is not int or value["coded_bytes"] <= 0
                    or abs(value["coded_bytes"] * 8 / (16 * 128 * 128) - value["bpp"]) > 1e-9
                    or not finite(value["spatial_error"]) or not 0 <= value["spatial_error"] <= 2
                    or not finite(value["encode_decode_s"]) or value["encode_decode_s"] < 0
                    or not isinstance(value["decoded_sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", value["decoded_sha256"])):
                raise ValueError("invalid proxy/rate/hash/timing")
    if stage == "dev":
        from src.tasks.action_recognition import kinetics_category_index, _canon
        expected_label = kinetics_category_index(PRIMARY[0])[_canon(source["sequence_id"].split("/")[0])]
        if type(row["label"]) is not int or row["label"] != expected_label:
            raise ValueError("label differs from canonical K400 label")
        for m, decision in zip(row["measurements"], decisions(row, source, policy), strict=True):
            if m["choices"] != decision or set(m["arms"]) != set(ARMS):
                raise ValueError("frozen V10 choice changed or arms incomplete")
            for arm, values in m["arms"].items():
                if (set(values) != {"name", "bpp", "analyzers"} or values["name"] != decision[arm]
                        or values["bpp"] != m["candidates"][decision[arm]]["bpp"]
                        or set(values["analyzers"]) != set(MODELS)):
                    raise ValueError("arm stream/rate/analyzer mismatch")
                for score in values["analyzers"].values():
                    pred = score.get("predicted_class_index")
                    if (set(score) != {"predicted_class_index", "correct", "inference_s"}
                            or type(pred) is not int or not 0 <= pred < 400
                            or type(score["correct"]) is not bool or score["correct"] != (pred == expected_label)
                            or not finite(score["inference_s"]) or score["inference_s"] < 0):
                        raise ValueError("invalid analyzer prediction/correctness")
            for a in ARMS:
                for b in ARMS:
                    if decision[a] == decision[b] and m["arms"][a] != m["arms"][b]:
                        raise ValueError("same selected stream has inconsistent scores")


def load_shards(folders: list[Path], stage: str, plan: dict, context: dict) -> tuple[list, list, dict, str]:
    if len(folders) != SHARDS:
        raise ValueError("exactly four shard folders required")
    data, input_sha = load_inputs(stage, plan, context)
    seen, by_id, manifests, run_commits = set(), {}, [], set()
    weight_sets = set()
    for folder in folders:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        shard = manifest.get("shard")
        if type(shard) is not int or shard not in range(SHARDS) or shard in seen:
            raise ValueError("duplicate or invalid shard")
        sources = data["sources"][shard::SHARDS]
        raw, proxy = folder / "shard_records.jsonl", folder / "proxy_records.jsonl"
        if (manifest.get("kind") != "shard" or manifest.get("stage") != stage
                or not matches_context(manifest.get("provenance", {}), context)
                or manifest.get("shards") != SHARDS or manifest.get("n") != len(sources)
                or manifest.get("source_ids") != [s["sequence_id"] for s in sources]
                or manifest.get("input_sha256") != input_sha
                or manifest.get("source_fingerprint") != plan["source_fingerprints"][stage]
                or manifest.get("calibration_sha256") != data["calibration_sha256"]
                or manifest.get("records_sha256") != sha256(raw)
                or manifest.get("proxy_records_sha256") != sha256(proxy)
                or manifest.get("trial_encode_decode_count") != len(sources) * 30):
            raise ValueError("shard manifest/provenance/hash mismatch")
        worker_commit = manifest["provenance"]["code_commit"]
        if not re.fullmatch(r"[0-9a-f]{40}", worker_commit):
            raise ValueError("invalid worker commit")
        git("merge-base", "--is-ancestor", worker_commit, "HEAD")
        run_commits.add(worker_commit)
        weights = manifest.get("weight_state_sha256", {})
        if stage == "dev":
            if set(weights) != set(MODELS) or any(not re.fullmatch(r"[0-9a-f]{64}", v) for v in weights.values()):
                raise ValueError("missing analyzer weight fingerprints")
        elif weights:
            raise ValueError("analyzer weights unexpectedly present in CAL proxy job")
        weight_sets.add(json.dumps(weights, sort_keys=True))
        rows = [json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()]
        decisions_only = [json.loads(line) for line in proxy.read_text(encoding="utf-8").splitlines()]
        if len(rows) != len(sources) or len(decisions_only) != len(sources):
            raise ValueError("incomplete shard")
        for row, old, source in zip(rows, decisions_only, sources, strict=True):
            validate_record(row, source, stage, data["policy"])
            view = {k: v for k, v in row.items() if k != "label"}
            view["measurements"] = [{k: v for k, v in m.items() if k != "arms"} for m in row["measurements"]]
            if view != old or row["sequence_id"] in by_id:
                raise ValueError("pre-inference choices changed or source overlap")
            by_id[row["sequence_id"]] = row
        seen.add(shard)
        manifests.append({**manifest, "manifest_sha256": sha256(folder / "manifest.json")})
    if len(run_commits) != 1 or len(weight_sets) != 1 or seen != set(range(SHARDS)) or len(by_id) != 200:
        raise ValueError("mixed code revisions or incomplete/overlapping cohort")
    return ([by_id[s["sequence_id"]] for s in data["sources"]],
            sorted(manifests, key=lambda m: m["shard"]), data, input_sha)


def primary_feasible(report: dict) -> bool:
    for model in PRIMARY:
        m = report[model]["metrics"]
        if (not all(finite(m.get(k)) for k in ("bd_rate_top1_pct", "bd_accuracy_top1", "min_same_qp_top1_gap"))
                or m["bd_rate_top1_pct"] >= -10 or m["bd_accuracy_top1"] <= 0
                or m["min_same_qp_top1_gap"] < -0.01 - 1e-12):
            return False
    return True


def selected_arrays(rows: list, pixels: list, sources: list, policy: dict | None, arm: str):
    values, excess, counts = [], [], {str(qp): Counter() for qp in QPS}
    for row, pixel, source in zip(rows, pixels, sources, strict=True):
        picked = decisions(pixel, source, policy) if policy else None
        video = []
        for i, (m, proxy, fixed) in enumerate(zip(row["measurements"], pixel["measurements"], source["measurements"], strict=True)):
            name = (picked[i]["v10"] if arm == "v10" else
                    "identity128" if arm == "identity" else fixed[arm])
            candidate = next(c for c in m["candidates"] if c["name"] == name)
            video.append([candidate["bpp"], *[float(candidate[f]) for f in FIELDS]])
            excess.append(max(0.0, proxy["candidates"][name]["spatial_error"] - proxy["candidates"]["identity128"]["spatial_error"]))
            counts[str(m["qp"])][name] += 1
        values.append(video)
    return np.asarray(values, dtype=np.float64), float(np.mean(excess)), {q: dict(v) for q, v in counts.items()}


def rate_distortion_diagnostic(rows: list, pixels: list) -> dict:
    result = {}
    for i, qp in enumerate(QPS):
        savings, excess = [], []
        gaps = {m: [] for m in PRIMARY}
        for row, pixel in zip(rows, pixels, strict=True):
            p = pixel["measurements"][i]["candidates"]
            savings.append(100 * (1 - p["area112"]["bpp"] / p["identity128"]["bpp"]))
            excess.append(p["area112"]["spatial_error"] - p["identity128"]["spatial_error"])
            c = {c["name"]: c for c in row["measurements"][i]["candidates"]}
            for model, field in zip(PRIMARY, FIELDS, strict=True):
                gaps[model].append(100 * (int(c["area112"][field]) - int(c["identity128"][field])))
        result[str(qp)] = {"n": len(rows), "saving_pct_p10_p50_p90": np.quantile(savings, [.1, .5, .9]).tolist(),
                           "spatial_excess_p10_p50_p90": np.quantile(excess, [.1, .5, .9]).tolist(),
                           "area112_minus_identity_top1_pp": {m: float(np.mean(v)) for m, v in gaps.items()}}
    return result


def calibrate(folders: list[Path], cache_root: Path, plan: dict, context: dict) -> dict:
    out = REPO / FROZEN
    if out.exists():
        raise ValueError("CAL result already exists; no repeated selection")
    pixels, manifests, data, input_sha = load_shards(folders, "calibration", plan, context)
    rows, _, _ = historical_stage(cache_root, "calibration")
    if [r["sequence_id"] for r in rows] != [r["sequence_id"] for r in pixels]:
        raise ValueError("CAL correctness/proxy join mismatch")
    identity, _, _ = selected_arrays(rows, pixels, data["sources"], None, "identity")
    grid = []
    for policy in policy_grid([r["complexity"] for r in pixels]):
        values, excess, counts = selected_arrays(rows, pixels, data["sources"], policy, "v10")
        report = metrics(identity, values)
        feasible = primary_feasible(report)
        rates = [report[m]["metrics"]["bd_rate_top1_pct"] for m in PRIMARY]
        grid.append({"policy": policy, "feasible": feasible, "analyzers": report,
                     "mean_spatial_excess": excess, "choices_by_qp": counts,
                     "worst_primary_bd_rate": max(rates) if feasible else None,
                     "sum_primary_bd_rate": sum(rates) if feasible else None})
    feasible = [r for r in grid if r["feasible"]]
    chosen = min(feasible, key=rank_key) if feasible else None
    baselines = {}
    for arm in ("v2", "v6"):
        values, excess, counts = selected_arrays(rows, pixels, data["sources"], None, arm)
        baselines[arm] = {"analyzers": metrics(identity, values), "mean_spatial_excess": excess, "choices_by_qp": counts}
    result = {"kind": "calibration_result", "provenance": context, "n": len(rows), "input_sha256": input_sha,
              "source_fingerprint": plan["source_fingerprints"]["calibration"], "shard_manifests": manifests,
              "grid": grid, "selected_policy": chosen["policy"] if chosen else None,
              "status": "FREEZE_BEFORE_DEV" if chosen else "NO_GO_STOP_BEFORE_DEV",
              "baselines": baselines, "identity_area112_by_qp": rate_distortion_diagnostic(rows, pixels),
              "mc3_18": "CHƯA ĐO; unavailable to CAL selection", "holdout": "CHƯA ĐO"}
    write_json(out, result)
    return {"path": str(out), "sha256": sha256(out), "selected_policy": result["selected_policy"], "status": result["status"]}


def engineering_gate(main: dict) -> dict:
    checks = {}
    for model in MODELS:
        values = main[model]["metrics"]
        intervals = main[model]["bootstrap"]
        rate, acc, gap = (values.get(k) for k in ("bd_rate_top1_pct", "bd_accuracy_top1_pp", "min_same_qp_top1_gap_pp"))
        checks[model] = {"rate": finite(rate) and rate < (-10 if model in PRIMARY else 0),
                         "accuracy": finite(acc) and acc > 0,
                         "same_qp": finite(gap) and gap >= -1.0 - 1e-9,
                         "bootstrap_valid": all(1900 <= intervals[k]["valid_draws"] <= DRAWS
                                                and intervals[k]["requested_draws"] == DRAWS
                                                and valid_ci(intervals[k].get("ci95"))
                                                for k in ("bd_rate_top1_pct", "bd_accuracy_top1_pp"))}
        if model == "mc3_18":
            ci = intervals["bd_rate_top1_pct"].get("ci95")
            checks[model]["ci_upper"] = (isinstance(ci, list) and len(ci) == 2
                                          and all(finite(v) for v in ci) and ci[0] <= ci[1] <= 1)
    return {"go_no_go": all(all(v.values()) for v in checks.values()), "checks": checks}


def valid_ci(ci) -> bool:
    return isinstance(ci, list) and len(ci) == 2 and all(finite(v) for v in ci) and ci[0] <= ci[1]


def merge(folders: list[Path], out: Path, plan: dict, context: dict) -> dict:
    if out.exists():
        raise ValueError("fresh merged output required")
    rows, manifests, data, input_sha = load_shards(folders, "dev", plan, context)
    resamples = np.random.default_rng(SEED).integers(0, len(rows), size=(DRAWS, len(rows)))
    comparisons = {}
    for name, anchor, trial in (("V2-C_vs_identity", "identity", "v2"), ("V6_vs_identity", "identity", "v6"),
                                ("area112_vs_identity", "identity", "area112"), ("V10_vs_identity", "identity", "v10"),
                                ("V10_vs_V2-C", "v2", "v10"), ("V10_vs_V6", "v6", "v10")):
        comparisons[name] = {m: summarize(rows, anchor, trial, m, resamples) for m in MODELS}
    main = comparisons["V10_vs_identity"]
    counts = {str(q): {a: dict(Counter(r["measurements"][i]["choices"][a] for r in rows))
                      for a in ("v2", "v6", "v10")} for i, q in enumerate(QPS)}
    original_point_gate = all(finite(main[m]["metrics"]["bd_rate_top1_pct"])
                              and main[m]["metrics"]["bd_rate_top1_pct"] < -15
                              and finite(main[m]["metrics"]["bd_accuracy_top1_pp"])
                              and main[m]["metrics"]["bd_accuracy_top1_pp"] > 0 for m in PRIMARY)
    result = {"kind": "dev_result", "provenance": context, "n": len(rows), "input_sha256": input_sha,
              "source_fingerprint": plan["source_fingerprints"]["dev"], "sources": plan["stages"]["dev"],
              "calibration_sha256": data["calibration_sha256"], "policy": data["policy"],
              "shard_manifests": manifests, "comparisons": comparisons, "choices_by_qp": counts,
              "original_primary_point_gate_on_reused_dev": original_point_gate, **engineering_gate(main),
              "original_gate": "NOT CONFIRMATORY: reused DEV; original threshold remains -15%",
              "holdout": "CHƯA ĐO"}
    write_json(out, result)
    return {"path": str(out), "sha256": sha256(out), "go_no_go": result["go_no_go"], "checks": result["checks"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg-commit", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--stage", choices=INPUTS, required=True)
    prepare.add_argument("--cache-root", type=Path, required=True)
    shard = commands.add_parser("shard")
    shard.add_argument("--stage", choices=INPUTS, required=True)
    shard.add_argument("--source-root", type=Path, required=True)
    shard.add_argument("--shard", type=int, choices=range(SHARDS), required=True)
    shard.add_argument("--out-dir", type=Path, required=True)
    cal = commands.add_parser("calibrate")
    cal.add_argument("--shard-dir", type=Path, action="append", required=True)
    cal.add_argument("--cache-root", type=Path, required=True)
    merged = commands.add_parser("merge")
    merged.add_argument("--shard-dir", type=Path, action="append", required=True)
    merged.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plan, context = protocol(args.prereg_commit)
    if args.command == "preflight":
        result = context
    elif args.command == "prepare":
        result = prepare_inputs(args.cache_root, args.stage, plan, context)
    elif args.command == "shard":
        result = run_shard(args.source_root, args.stage, args.shard, args.out_dir, plan, context)
    elif args.command == "calibrate":
        result = calibrate(args.shard_dir, args.cache_root, plan, context)
    else:
        result = merge(args.shard_dir, args.out, plan, context)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
