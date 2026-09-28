#!/usr/bin/env python
"""V7 H.265 CAL/DEV search using frozen V6 models and pixel proxy shards."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import re

import numpy as np

from ops.dual_codec_search import FIELDS, bootstrap, digest, metrics, validate_row, write_json
from ops.v5_dev_agreement import load_locked_dev_cache
from ops.v6_dev_residual import predicted_measurements, select_residual
from ops.v6_frozen import load_frozen_v6, frozen_manifest
from ops.v7_pixel_proxy import (PLAN_SHA256, REPO, STAGES, sha256,
                                verify_protocol)
from src.models.codec_search import CANDIDATES
from src.models.dual_codec_search import MODELS

SEED = 20261003
DRAWS = 2000
THRESHOLDS = (0.0, -0.02)
WEIGHTS = (0.25, 0.5, 1.0, 2.0)
TOLERANCE_PP = 1.0
MIN_GAP = -0.01


def load_cache_stage(root: Path, stage: str, plan: dict, lock: dict) -> tuple[list, dict, dict]:
    """Validate and read exactly one locked stage; never preload DEV at CAL."""
    if root.name != "h265" or root.parent.name != "dual_codec_search_v2":
        raise ValueError("only the locked H.265 V2 pilot cache is allowed")
    expected = lock["input_provenance"]["h265"]
    manifest_path = root / "manifest.json"
    risk_path = root / "risk_model.json"
    policy_path = root / "frozen_policy.json"
    for path, key in ((manifest_path, "manifest_sha256"),
                      (risk_path, "risk_model_sha256"),
                      (policy_path, "frozen_policy_sha256")):
        if sha256(path) != expected[key]:
            raise ValueError(f"locked V2 {key} changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    risk = json.loads(risk_path.read_text(encoding="utf-8"))
    frozen = json.loads(policy_path.read_text(encoding="utf-8"))
    if (manifest.get("experiment") != "dual_codec_search_v2_pilot"
            or manifest.get("codec") != "h265"
            or manifest.get("split_fingerprints") != plan["source_fingerprints"]
            or manifest["split_ids"] != plan["stage_ids"]
            or frozen["manifest_sha256"] != digest(manifest)
            or frozen["risk_sha256"] != digest(risk)
            or frozen["selected_policy"]["mode"] != "C"):
        raise ValueError("locked V2 cache manifest or comparator changed")
    ids = plan["stage_ids"][stage]
    files = sorted((root / "cache" / stage).glob("clip_*.json"))
    if len(files) != len(ids):
        raise ValueError(f"incomplete {stage} cache")
    rows, tree = {}, hashlib.sha256()
    cache_key = digest(manifest)
    for path in files:
        row = json.loads(path.read_text(encoding="utf-8"))
        key = row["sequence_id"]
        if key in rows:
            raise ValueError(f"duplicate {stage} source")
        validate_row(row, key, "h265", cache_key)
        rows[key] = row
        tree.update(f"{path.name}\t{sha256(path)}\n".encode())
    if set(rows) != set(ids) or tree.hexdigest() != expected["cache_tree_sha256"][stage]:
        raise ValueError(f"{stage} source IDs or record bytes changed")
    return [rows[key] for key in ids], risk, frozen["selected_policy"]


def load_proxy_stage(root: Path, stage: str, plan: dict, commit: str) -> tuple[dict, dict]:
    folder = root / stage
    manifest_path, records_path = folder / "manifest.json", folder / "shard_records.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = plan["stage_ids"][stage]
    if (manifest.get("experiment") != "v7_h265_dev_pixel_proxy"
            or manifest.get("stage") != stage or manifest.get("n") != len(ids)
            or manifest.get("source_ids") != ids
            or manifest.get("source_fingerprint") != plan["source_fingerprints"][stage]
            or manifest.get("plan_sha256") != PLAN_SHA256
            or manifest.get("code_commit") != commit
            or manifest.get("records_sha256") != sha256(records_path)):
        raise ValueError(f"V7 {stage} pixel shard differs from protocol")
    by_id = {}
    with records_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            key = record["sequence_id"]
            if (key in by_id or key not in ids
                    or not re.fullmatch(r"[0-9a-f]{64}", record["source_sha256"])):
                raise ValueError(f"invalid/duplicate V7 {stage} source record")
            values = record["proxy_by_candidate"]
            if set(values) != set(CANDIDATES):
                raise ValueError("V7 candidate proxy set changed")
            for candidate in CANDIDATES:
                if set(values[candidate]) != {"spatial", "temporal", "proxy"}:
                    raise ValueError("V7 proxy schema changed")
                numbers = list(values[candidate].values())
                if (not np.isfinite(numbers).all() or min(numbers) < 0
                        or max(numbers) > 2
                        or values[candidate]["proxy"]
                           != max(values[candidate]["spatial"], values[candidate]["temporal"])):
                    raise ValueError("invalid V7 pixel proxy")
            if values["identity128"]["proxy"] != 0:
                raise ValueError("V7 identity pixel proxy changed")
            by_id[key] = record
    if set(by_id) != set(ids):
        raise ValueError(f"V7 {stage} pixel shard missing sources")
    return by_id, {"manifest_sha256": sha256(manifest_path),
                   "records_sha256": sha256(records_path),
                   "source_video_sha256": {key: by_id[key]["source_sha256"] for key in ids}}


def policy_grid() -> list[dict]:
    return [{"mode": "V7_pixel", "threshold": threshold, "pixel_weight": weight}
            for threshold, weight in product(THRESHOLDS, WEIGHTS)]


def choose_v7(obs: list[dict], v6: int, probabilities: np.ndarray,
              proxy: dict, policy: dict) -> int:
    if (policy.get("mode") != "V7_pixel" or policy.get("threshold") not in THRESHOLDS
            or policy.get("pixel_weight") not in WEIGHTS
            or v6 not in range(len(CANDIDATES))
            or probabilities.shape != (len(CANDIDATES), len(MODELS), 2)
            or not np.isfinite(probabilities).all()
            or [row["name"] for row in obs] != list(CANDIDATES)):
        raise ValueError("invalid V7 selection inputs")
    expected = probabilities[:, :, 1] - probabilities[:, :, 0]
    feasible = [v6]
    for index in range(len(CANDIDATES)):
        if (index != v6 and obs[index]["bpp"] <= obs[0]["bpp"]
                and np.all(expected[index] - expected[v6] >= policy["threshold"])):
            feasible.append(index)
    weight = policy["pixel_weight"]
    return min(feasible, key=lambda index: (
        math.log(obs[index]["bpp"] / obs[0]["bpp"])
        + weight * proxy[obs[index]["name"]]["proxy"], index))


def selected_arrays(prepared: list, rows: list, pixel: dict,
                    v6_policy: dict, policy: dict | None) -> tuple[np.ndarray, np.ndarray, dict]:
    values, proxies, choices = [], [], Counter()
    for row, video in zip(rows, prepared, strict=True):
        source_proxy = pixel[row["sequence_id"]]["proxy_by_candidate"]
        clip_values, clip_proxy = [], []
        for measurement, obs, base, probabilities in video:
            v6 = select_residual(obs, base, probabilities, v6_policy)
            index = v6 if policy is None else choose_v7(obs, v6, probabilities,
                                                         source_proxy, policy)
            candidate = measurement["candidates"][index]
            clip_values.append([candidate["bpp"],
                                *[float(candidate[field]) for field in FIELDS]])
            clip_proxy.append(source_proxy[candidate["name"]]["proxy"])
            choices[candidate["name"]] += 1
        values.append(clip_values)
        proxies.append(clip_proxy)
    return np.asarray(values, dtype=np.float64), np.asarray(proxies), dict(choices)


def identity_arrays(rows: list) -> np.ndarray:
    return np.asarray([[[m["candidates"][0]["bpp"],
                         *[float(m["candidates"][0][field]) for field in FIELDS]]
                        for m in row["measurements"]] for row in rows], dtype=np.float64)


def primary_feasible(report: dict, v6_report: dict,
                     proxy: float, v6_proxy: float) -> bool:
    if not np.isfinite(proxy) or proxy >= v6_proxy:
        return False
    for model in MODELS:
        current, baseline = report[model]["metrics"], v6_report[model]["metrics"]
        rate, old_rate = current["bd_rate_top1_pct"], baseline["bd_rate_top1_pct"]
        accuracy, gap = current["bd_accuracy_top1"], current["min_same_qp_top1_gap"]
        if (any(x is None for x in (rate, old_rate, accuracy, gap))
                or not np.isfinite([rate, old_rate, accuracy, gap]).all()
                or rate >= -10.0 or rate > old_rate + TOLERANCE_PP
                or accuracy <= 0 or gap < MIN_GAP):
            return False
    return True


def calibrate(rows: list, pixel: dict, risk: dict, v2_policy: dict,
              models: dict, v6_policy: dict) -> dict:
    prepared = predicted_measurements(rows, risk, v2_policy, models)
    identity = identity_arrays(rows)
    v6, v6_proxy, v6_choices = selected_arrays(prepared, rows, pixel, v6_policy, None)
    v6_report = metrics(identity, v6)
    grid = []
    for policy in policy_grid():
        trial, proxy, choices = selected_arrays(prepared, rows, pixel, v6_policy, policy)
        report = metrics(identity, trial)
        feasible = primary_feasible(report, v6_report, float(proxy.mean()),
                                    float(v6_proxy.mean()))
        rates = [report[model]["metrics"]["bd_rate_top1_pct"] for model in MODELS]
        grid.append({"policy": policy, "feasible": feasible,
                     "mean_proxy": float(proxy.mean()),
                     "proxy_delta_vs_v6": float(proxy.mean() - v6_proxy.mean()),
                     "worst_bd_rate": max(rates) if feasible else None,
                     "sum_bd_rate": sum(rates) if feasible else None,
                     "analyzers": {model: report[model]["metrics"] for model in MODELS},
                     "choices": choices})
    feasible_rows = [row for row in grid if row["feasible"]]
    chosen = min(feasible_rows, key=lambda row: (
        row["mean_proxy"], row["worst_bd_rate"], row["sum_bd_rate"],
        row["policy"]["threshold"], row["policy"]["pixel_weight"])) if feasible_rows else None
    return {"grid": grid, "selected_policy": chosen["policy"] if chosen else None,
            "selected_calibration_point": chosen,
            "v6_calibration_point": {m: v6_report[m]["metrics"] for m in MODELS},
            "v6_mean_proxy": float(v6_proxy.mean()), "v6_choices": v6_choices}


def proxy_bootstrap(v6: np.ndarray, trial: np.ndarray) -> dict:
    paired = (trial - v6).mean(axis=1)
    rng = np.random.default_rng(SEED)
    draws = [float(paired[rng.integers(0, len(paired), len(paired))].mean())
             for _ in range(DRAWS)]
    return {"point": float(paired.mean()), "ci95": np.percentile(draws, [2.5, 97.5]).tolist(),
            "valid_draws": DRAWS, "requested_draws": DRAWS}


def evaluate_dev(rows: list, pixel: dict, risk: dict, v2_policy: dict,
                 models: dict, v6_policy: dict, policy: dict) -> dict:
    prepared = predicted_measurements(rows, risk, v2_policy, models)
    identity = identity_arrays(rows)
    v2 = np.asarray([[[measurement["candidates"][base]["bpp"],
                       *[float(measurement["candidates"][base][field]) for field in FIELDS]]
                      for measurement, _, base, _ in video]
                     for video in prepared], dtype=np.float64)
    v6, old_proxy, old_choices = selected_arrays(prepared, rows, pixel, v6_policy, None)
    v7, new_proxy, new_choices = selected_arrays(prepared, rows, pixel, v6_policy, policy)
    comparisons = {}
    for name, anchor, trial in (("V2-C_vs_identity", identity, v2),
                                ("V6_vs_identity", identity, v6),
                                ("V7_vs_identity", identity, v7),
                                ("V7_vs_V6", v6, v7)):
        comparisons[name] = {"analyzers": metrics(anchor, trial),
                             "bootstrap": bootstrap(anchor, trial, DRAWS, SEED)}
    go = primary_feasible(comparisons["V7_vs_identity"]["analyzers"],
                          comparisons["V6_vs_identity"]["analyzers"],
                          float(new_proxy.mean()), float(old_proxy.mean()))
    return {"comparisons": comparisons,
            "pixel_proxy": {"V6_mean": float(old_proxy.mean()),
                            "V7_mean": float(new_proxy.mean()),
                            "paired_delta": proxy_bootstrap(old_proxy, new_proxy)},
            "choices": {"V6": old_choices, "V7": new_choices},
            "go_no_go_this_codec": go}


def run(cache_root: Path, pixel_root: Path, out_dir: Path) -> dict:
    plan, commit = verify_protocol()
    if out_dir.exists():
        raise ValueError("V7 output directory must be new")
    lock, lock_sha = load_locked_dev_cache()
    v6_manifest = frozen_manifest()
    v6_policy, models = load_frozen_v6()
    cal, risk, v2_policy = load_cache_stage(cache_root, "calibration", plan, lock)
    cal_pixel, cal_pixel_hashes = load_proxy_stage(pixel_root, "calibration", plan, commit)
    selection = calibrate(cal, cal_pixel, risk, v2_policy, models, v6_policy)
    assessment, dev_pixel_hashes = None, None
    if selection["selected_policy"] is not None:
        dev, dev_risk, dev_v2_policy = load_cache_stage(cache_root, "dev", plan, lock)
        if dev_risk != risk or dev_v2_policy != v2_policy:
            raise ValueError("CAL and DEV V2 comparator differs")
        dev_pixel, dev_pixel_hashes = load_proxy_stage(pixel_root, "dev", plan, commit)
        assessment = evaluate_dev(dev, dev_pixel, risk, v2_policy, models,
                                  v6_policy, selection["selected_policy"])
    report = {"experiment": "v7_h265_dev_pixel_proxy", "scope": "CAL/DEV only; no mc3 or holdout outcome",
              "preregistration_commit": "6c4a03d4e95d3f549adddf0a890704a334eb3a39",
              "analysis_code_commit": commit, "codec": "h265",
              "source_fingerprints": {stage: plan["source_fingerprints"][stage] for stage in STAGES},
              "source_plan_sha256": PLAN_SHA256,
              "dev_cache_manifest_sha256": lock_sha,
              "dev_cache_archive_sha256": lock["archive_sha256"],
              "frozen_v6_manifest_sha256": sha256(REPO / "configs/v6_h265_frozen/manifest.json"),
              "frozen_v6_model_sha256": v6_manifest["model_sha256"],
              "pixel_shards": {"calibration": cal_pixel_hashes, "dev": dev_pixel_hashes},
              "bootstrap_unit": "source video; all QPs and arms paired",
              "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
              "policy_grid": policy_grid(), "calibration": selection, "dev": assessment}
    out_dir.mkdir(parents=True)
    result_path = out_dir / "h265_result.json"
    write_json(result_path, report)
    result_sha = sha256(result_path)
    (out_dir / "h265_result.sha256").write_text(
        f"{result_sha}  h265_result.json\n", encoding="ascii")
    return {"selected_policy": selection["selected_policy"],
            "dev_go_no_go": (assessment or {}).get("go_no_go_this_codec"),
            "result_sha256": result_sha}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--pixel-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.cache_root, args.pixel_root, args.out_dir), indent=2))


if __name__ == "__main__":
    main()
