#!/usr/bin/env python
"""Preregistered V4 FIT/CALIBRATION/DEV correctness selector.

This command opens only the original pilot development manifest and its three
stage caches. It never reads old TEST/holdout records or mc3 outcomes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from ops.dual_codec_search import (FIELDS, bootstrap, digest, eligible, metrics,
                                   prepare, selected_arrays, validate_row, write_json)
from ops.v3_dev_policy import (EXPECTED_FINGERPRINTS, REPO, file_sha256,
                               source_id)
from src.models.dual_codec_search import MODELS, observations, risk_features

PREREG_COMMIT = "17b036c6fb5819e67751dfd3be83193eb1097be9"
PILOT_INDEX_SHA256 = "1a7adb6ad3aac2fa3fc93767c9567e49441b35f7ad6375fe7e1949ef0507acb2"
COUNTS = {"fit": 400, "calibration": 200, "dev": 200}
THRESHOLDS = (-.05, 0., .05)
MODEL_PARAMS = {"loss": "log_loss", "learning_rate": .05,
                "max_iter": 100, "max_leaf_nodes": 15,
                "min_samples_leaf": 40, "l2_regularization": 1.,
                "early_stopping": False, "random_state": 53}
SEED = 20260928
DRAWS = 2000


def verify_preregistration() -> str:
    git = ["git", "-c", f"safe.directory={REPO.as_posix()}"]
    subprocess.run(git + ["merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD"],
                   cwd=REPO, check=True)
    locked = subprocess.check_output(
        git + ["show", f"{PREREG_COMMIT}:docs/PREREGISTRATION_V4.md"], cwd=REPO)
    current = (REPO / "docs/PREREGISTRATION_V4.md").read_bytes()
    if current.replace(b"\r\n", b"\n") != locked:
        raise ValueError("V4 preregistration changed after lock")
    subprocess.run(git + ["ls-files", "--error-unmatch", "ops/v4_dev_policy.py"],
                   cwd=REPO, check=True, capture_output=True)
    subprocess.run(git + ["diff", "--quiet", "HEAD", "--", "ops/v4_dev_policy.py"],
                   cwd=REPO, check=True)
    return subprocess.check_output(git + ["rev-parse", "HEAD"], cwd=REPO,
                                   text=True).strip()


def load_development(root: Path, codec: str) -> tuple[list, list, list, dict, dict, dict]:
    root = root.resolve()
    if root.name != codec or root.parent.name != "dual_codec_search_v2":
        raise ValueError("only original V2 pilot development cache is allowed")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("experiment") != "dual_codec_search_v2_pilot"
            or manifest.get("codec") != codec
            or manifest.get("split_fingerprints") != EXPECTED_FINGERPRINTS
            or {stage: len(manifest["split_ids"][stage]) for stage in COUNTS}
            != COUNTS):
        raise ValueError("development manifest differs from locked source")
    if any(digest(manifest["split_ids"][stage]) != EXPECTED_FINGERPRINTS[stage]
           for stage in COUNTS):
        raise ValueError("development IDs differ from locked fingerprints")
    sets = {stage: {source_id(key) for key in manifest["split_ids"][stage]}
            for stage in COUNTS}
    if (any(len(sets[stage]) != COUNTS[stage] for stage in COUNTS)
            or any(sets[a] & sets[b] for a, b in
                   (("fit", "calibration"), ("fit", "dev"), ("calibration", "dev")))):
        raise ValueError("development source overlap")
    frozen_path = root / "frozen_policy.json"
    risk_path = root / "risk_model.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    risk = json.loads(risk_path.read_text(encoding="utf-8"))
    cache_key = digest(manifest)
    if (frozen["manifest_sha256"] != cache_key
            or frozen["risk_sha256"] != digest(risk)
            or frozen["selected_policy"]["mode"] != "C"):
        raise ValueError("V2-C frozen comparator changed")
    stages, tree_hashes = {}, {}
    for stage, count in COUNTS.items():
        files = sorted((root / "cache" / stage).glob("clip_*.json"))
        if len(files) != count:
            raise ValueError(f"incomplete {codec} {stage} cache")
        by_id = {}
        tree = hashlib.sha256()
        for path in files:
            row = json.loads(path.read_text(encoding="utf-8"))
            key = row["sequence_id"]
            if key in by_id:
                raise ValueError("duplicate development record")
            validate_row(row, key, codec, cache_key)
            by_id[key] = row
            tree.update(f"{path.name}\t{file_sha256(path)}\n".encode())
        ids = manifest["split_ids"][stage]
        if set(by_id) != set(ids):
            raise ValueError(f"{codec} {stage} IDs changed")
        stages[stage] = [by_id[key] for key in ids]
        tree_hashes[stage] = tree.hexdigest()
    provenance = {"manifest_sha256": file_sha256(manifest_path),
                  "index_sha256": PILOT_INDEX_SHA256,
                  "risk_model_sha256": file_sha256(risk_path),
                  "frozen_policy_sha256": file_sha256(frozen_path),
                  "cache_tree_sha256": tree_hashes,
                  "source_fingerprints": EXPECTED_FINGERPRINTS}
    return (stages["fit"], stages["calibration"], stages["dev"],
            risk, frozen["selected_policy"], provenance)


def features_and_labels(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    features, labels = [], []
    for row in rows:
        for measurement in row["measurements"]:
            obs = observations(measurement["candidates"])
            for index, candidate in enumerate(measurement["candidates"]):
                features.append(risk_features(obs, index, measurement["qp"]))
                labels.append([int(candidate[field]) for field in FIELDS])
    x, y = np.asarray(features), np.asarray(labels)
    if x.shape[0] != 12000 or y.shape != (12000, 2) or not np.isfinite(x).all():
        raise ValueError("FIT features are incomplete or non-finite")
    if any(set(np.unique(y[:, j])) != {0, 1} for j in range(2)):
        raise ValueError("FIT correctness target has one class")
    return x, y


def fit_models(rows: list[dict]) -> tuple[dict, dict]:
    x, y = features_and_labels(rows)
    models = {}
    for index, name in enumerate(MODELS):
        model = HistGradientBoostingClassifier(**MODEL_PARAMS)
        model.fit(x, y[:, index], sample_weight=np.ones(len(x)))
        if list(model.classes_) != [0, 1]:
            raise ValueError("unexpected correctness class order")
        models[name] = model
    return models, {"n_fit_sources": len(rows), "n_fit_rows": len(x),
                    "positive_rows": dict(zip(MODELS, y.sum(axis=0).astype(int).tolist()))}


def predicted_measurements(rows: list[dict], models: dict) -> list:
    features, raw = [], []
    for row in rows:
        video = []
        for measurement in row["measurements"]:
            obs = observations(measurement["candidates"])
            features.extend(risk_features(obs, index, measurement["qp"])
                            for index in range(len(obs)))
            video.append((measurement, obs))
        raw.append(video)
    x = np.asarray(features)
    n = len(rows)
    if x.shape[0] != n * 5 * 6 or not np.isfinite(x).all():
        raise ValueError("candidate feature shape changed")
    p = np.stack([models[name].predict_proba(x)[:, 1] for name in MODELS], axis=1)
    if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("invalid correctness probability")
    p = p.reshape(n, 5, 6, 2)
    return [[(measurement, obs, p[i, q])
             for q, (measurement, obs) in enumerate(video)]
            for i, video in enumerate(raw)]


def policy_grid() -> list[dict]:
    return [{"mode": "P4", "thresholds_low": dict(zip(MODELS, (lr, l3))),
             "thresholds_high": dict(zip(MODELS, (hr, h3)))}
            for lr, l3, hr, h3 in product(THRESHOLDS, repeat=4)]


def threshold_tuple(policy: dict) -> tuple[float, float, float, float]:
    return (policy["thresholds_low"][MODELS[0]],
            policy["thresholds_low"][MODELS[1]],
            policy["thresholds_high"][MODELS[0]],
            policy["thresholds_high"][MODELS[1]])


def select_probability(obs: list[dict], probabilities: np.ndarray,
                       qp: int, policy: dict) -> int:
    if policy.get("mode") != "P4" or probabilities.shape != (len(obs), 2):
        raise ValueError("V4 needs candidate observations and two probability models")
    if not np.isfinite(probabilities).all():
        raise ValueError("non-finite correctness probability")
    thresholds = policy["thresholds_low"] if qp <= 35 else policy["thresholds_high"]
    feasible = [0]
    for index, candidate in enumerate(obs[1:], 1):
        if candidate["bpp"] >= obs[0]["bpp"]:
            continue
        if all(probabilities[index, j] - probabilities[0, j] >= thresholds[model]
               for j, model in enumerate(MODELS)):
            feasible.append(index)
    return min(feasible, key=lambda index: obs[index]["bpp"])


def selected_arrays_v4(prepared: list, policy: dict) -> tuple[np.ndarray, dict]:
    values, choices = [], Counter()
    for video in prepared:
        selections = []
        for measurement, obs, probabilities in video:
            index = select_probability(obs, probabilities, measurement["qp"], policy)
            candidate = measurement["candidates"][index]
            selections.append([candidate["bpp"],
                               *[float(candidate[field]) for field in FIELDS]])
            choices[candidate["name"]] += 1
        values.append(selections)
    return np.asarray(values), dict(choices)


def point(report: dict) -> dict:
    return {model: report[model]["metrics"] for model in MODELS}


def calibrate(rows: list[dict], risk: dict, old_policy: dict,
              models: dict) -> dict:
    old_prepared = prepare(rows, risk)
    base, _ = selected_arrays(old_prepared, {"mode": "identity"})
    old, old_choices = selected_arrays(old_prepared, old_policy)
    old_report = metrics(base, old)
    if not eligible(old_report):
        raise ValueError("frozen V2-C comparator is invalid on CALIBRATION")
    prepared = predicted_measurements(rows, models)
    grid = []
    for policy in policy_grid():
        trial, choices = selected_arrays_v4(prepared, policy)
        report = metrics(base, trial)
        okay = eligible(report)
        br = [report[model]["metrics"]["bd_rate_top1_pct"] for model in MODELS]
        grid.append({"policy": policy, "thresholds": threshold_tuple(policy),
                     "eligible": okay, "worst_bd_rate": max(br) if okay else None,
                     "sum_bd_rate": sum(br) if okay else None,
                     "analyzers": point(report), "choices": choices})
    feasible = [row for row in grid if row["eligible"]]
    best = min(feasible, key=lambda row: (row["worst_bd_rate"],
               row["sum_bd_rate"], row["thresholds"])) if feasible else None
    old_br = {model: old_report[model]["metrics"]["bd_rate_top1_pct"]
              for model in MODELS}
    promoted = bool(best is not None and
                    best["worst_bd_rate"] <= max(old_br.values()) - 1.0 and
                    all(best["analyzers"][model]["bd_rate_top1_pct"] <=
                        old_br[model] + .5 for model in MODELS))
    return {"grid": grid, "best_grid_policy": best["policy"] if best else None,
            "best_grid_point": best["analyzers"] if best else None,
            "old_policy": old_policy, "old_point": point(old_report),
            "old_choices": old_choices, "promoted": promoted,
            "selected_policy": best["policy"] if promoted else old_policy}


def evaluate_dev(rows: list[dict], risk: dict, old_policy: dict,
                 models: dict, selection: dict) -> dict:
    old_prepared = prepare(rows, risk)
    base, _ = selected_arrays(old_prepared, {"mode": "identity"})
    old, old_choices = selected_arrays(old_prepared, old_policy)
    if selection["promoted"]:
        prepared = predicted_measurements(rows, models)
        new, new_choices = selected_arrays_v4(prepared, selection["selected_policy"])
    else:
        new, new_choices = old.copy(), dict(old_choices)
    comparisons = {}
    for name, anchor, trial in (("V2-C_vs_identity", base, old),
                                ("V4_vs_identity", base, new),
                                ("V4_vs_V2-C", old, new)):
        comparisons[name] = {"analyzers": metrics(anchor, trial),
                             "bootstrap": bootstrap(anchor, trial, DRAWS, SEED)}
    new_point = comparisons["V4_vs_identity"]["analyzers"]
    old_point = comparisons["V2-C_vs_identity"]["analyzers"]
    go = selection["promoted"] and all(
        new_point[model]["metrics"]["bd_rate_top1_pct"] is not None and
        old_point[model]["metrics"]["bd_rate_top1_pct"] is not None and
        new_point[model]["metrics"]["bd_rate_top1_pct"] <
        old_point[model]["metrics"]["bd_rate_top1_pct"] and
        new_point[model]["metrics"]["bd_accuracy_top1"] is not None and
        new_point[model]["metrics"]["bd_accuracy_top1"] > 0 and
        new_point[model]["metrics"]["min_same_qp_top1_gap"] >= -.01
        for model in MODELS)
    return {"comparisons": comparisons,
            "choices": {"V2-C": old_choices, "V4": new_choices},
            "go_no_go_this_codec": go}


def run(roots: dict[str, Path], out_dir: Path) -> dict:
    code_commit = verify_preregistration()
    if set(roots) != {"h264", "h265"} or out_dir.exists():
        raise ValueError("both codecs required and output directory must be new")
    loaded = {codec: load_development(roots[codec], codec)
              for codec in ("h264", "h265")}
    # The same exact source plan must underlie both codecs.
    if loaded["h264"][5]["source_fingerprints"] != loaded["h265"][5]["source_fingerprints"]:
        raise ValueError("development source differs by codec")
    reports, fitted = {}, {}
    for codec in ("h264", "h265"):
        fit, calibration, dev, risk, old_policy, provenance = loaded[codec]
        models, fit_counts = fit_models(fit)
        selection = calibrate(calibration, risk, old_policy, models)
        assessment = evaluate_dev(dev, risk, old_policy, models, selection)
        fitted[codec] = models
        reports[codec] = {"experiment": "v4_dev_correctness_policy",
            "scope": "FIT/CALIBRATION/DEV only; fresh holdout not touched",
            "codec": codec, "preregistration_commit": PREREG_COMMIT,
            "analysis_code_commit": code_commit,
            "sklearn_version": sklearn.__version__,
            "model_params": MODEL_PARAMS, "threshold_grid": list(THRESHOLDS),
            "input_provenance": provenance, "fit_counts": fit_counts,
            "bootstrap_unit": "source video; all QPs, arms and analyzers paired",
            "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
            "selection": selection, "dev": assessment}
    out_dir.mkdir(parents=True)
    for codec, report in reports.items():
        model_dir = out_dir / "models" / codec
        model_dir.mkdir(parents=True)
        report["fitted_model_sha256"] = {}
        for name in MODELS:
            path = model_dir / f"{name}.joblib"
            joblib.dump(fitted[codec][name], path, compress=3)
            report["fitted_model_sha256"][name] = file_sha256(path)
        path = out_dir / f"{codec}_result.json"
        write_json(path, report)
        path.with_suffix(".sha256").write_text(
            f"{file_sha256(path)}  {path.name}\n", encoding="utf-8")
    return {codec: {"promoted": report["selection"]["promoted"],
                    "go_no_go_this_codec": report["dev"]["go_no_go_this_codec"],
                    "selected_policy": report["selection"]["selected_policy"]}
            for codec, report in reports.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h264-cache-root", type=Path, required=True)
    parser.add_argument("--h265-cache-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run({"h264": args.h264_cache_root,
                          "h265": args.h265_cache_root}, args.out_dir), indent=2))


if __name__ == "__main__":
    main()
