#!/usr/bin/env python
"""Preregistered V6 paired V2-C residual selector; FIT/CAL/DEV only."""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import product
import json
import math
from pathlib import Path
import subprocess

import joblib
import numpy as np
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ops.dual_codec_search import (FIELDS, bootstrap, metrics, prepare,
                                   selected_arrays, write_json)
from ops.v3_dev_policy import REPO, file_sha256
from ops.v4_dev_policy import load_development
from ops.v5_dev_agreement import (load_locked_dev_cache, verify_loaded_cache)
from src.models.dual_codec_search import (MODELS, observations, risk_features,
                                          risk_scores, select_observations)

PREREG_COMMIT = "efdf5e3d7bd0889c6dc09bc05dc12c928ffb1159"
SEED = 20260930
DRAWS = 2000
THRESHOLDS = (-0.05, -0.02, 0.0)
WEIGHTS = (0.0, 5.0, 20.0, 80.0)
MODEL_PARAMS = {"C": 1.0, "max_iter": 2000, "random_state": 53}
TOLERANCE_PP = 1.0
MIN_GAP = -0.01
EVENTS = ("harm", "gain")


def verify_preregistration() -> str:
    git = ["git", "-c", f"safe.directory={REPO.as_posix()}"]
    subprocess.run(git + ["merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD"],
                   cwd=REPO, check=True)
    locked = subprocess.check_output(
        git + ["show", f"{PREREG_COMMIT}:docs/PREREGISTRATION_V6.md"], cwd=REPO)
    if (REPO / "docs/PREREGISTRATION_V6.md").read_bytes().replace(b"\r\n", b"\n") != locked:
        raise ValueError("V6 preregistration changed after lock")
    for path in ("ops/v6_dev_residual.py", "kaggle/v6_dev_residual_cell.sh"):
        subprocess.run(git + ["ls-files", "--error-unmatch", path], cwd=REPO,
                       check=True, capture_output=True)
        subprocess.run(git + ["diff", "--quiet", "HEAD", "--", path],
                       cwd=REPO, check=True)
    return subprocess.check_output(git + ["rev-parse", "HEAD"], cwd=REPO,
                                   text=True).strip()


def policy_grid() -> list[dict]:
    return [{"mode": "V6", "minimum_expected_delta": threshold,
             "feature_weight": weight}
            for threshold, weight in product(THRESHOLDS, WEIGHTS)]


def pair_features(obs: list[dict], candidate: int, base: int, qp: int) -> np.ndarray:
    """Prediction features depend only on the label-free observations."""
    base_features = risk_features(obs, base, qp)
    candidate_features = risk_features(obs, candidate, qp)
    return np.concatenate((base_features, candidate_features - base_features))


def fit_event_models(rows: list[dict], risk: dict, old_policy: dict) -> tuple[dict, dict]:
    x, labels = [], {name: {event: [] for event in EVENTS} for name in MODELS}
    for row in rows:
        for measurement in row["measurements"]:
            obs = observations(measurement["candidates"])
            qp = measurement["qp"]
            base = select_observations(obs, qp, old_policy, risk_scores(obs, qp, risk))
            for index in range(len(obs)):
                if index == base:
                    continue
                x.append(pair_features(obs, index, base, qp))
                for model, field in zip(MODELS, FIELDS):
                    old_correct = bool(measurement["candidates"][base][field])
                    new_correct = bool(measurement["candidates"][index][field])
                    labels[model]["harm"].append(int(old_correct and not new_correct))
                    labels[model]["gain"].append(int(not old_correct and new_correct))
    features = np.asarray(x, dtype=np.float64)
    if (len(rows) != 400 or features.shape != (len(rows) * 5 * 5, 82)
            or not np.isfinite(features).all()):
        raise ValueError("unexpected V6 FIT feature shape or non-finite feature")
    models, counts = {}, {}
    for model in MODELS:
        models[model], counts[model] = {}, {}
        for event in EVENTS:
            target = np.asarray(labels[model][event], dtype=np.int64)
            positives = int(target.sum())
            counts[model][event] = {"positive": positives, "total": len(target)}
            if len(np.unique(target)) < 2:
                models[model][event] = {"constant": 1.0 if event == "harm" else 0.0}
            else:
                fitted = make_pipeline(StandardScaler(), LogisticRegression(**MODEL_PARAMS))
                fitted.fit(features, target)
                if list(fitted.classes_) != [0, 1]:
                    raise ValueError("unexpected V6 event class order")
                models[model][event] = fitted
    return models, counts


def event_probability(model: object, features: np.ndarray) -> np.ndarray:
    if isinstance(model, dict):
        return np.full(len(features), model["constant"], dtype=np.float64)
    return model.predict_proba(features)[:, 1]


def predicted_measurements(rows: list[dict], risk: dict, old_policy: dict,
                           models: dict) -> list:
    raw, feature_vectors = [], []
    for row in rows:
        video = []
        for measurement in row["measurements"]:
            obs = observations(measurement["candidates"])
            qp = measurement["qp"]
            base = select_observations(obs, qp, old_policy, risk_scores(obs, qp, risk))
            for index in range(len(obs)):
                feature_vectors.append(pair_features(obs, index, base, qp))
            video.append((measurement, obs, base))
        raw.append(video)
    x = np.asarray(feature_vectors, dtype=np.float64)
    if x.shape != (len(rows) * 5 * 6, 82) or not np.isfinite(x).all():
        raise ValueError("unexpected V6 prediction feature shape")
    predicted = np.stack([
        np.stack([event_probability(models[model][event], x) for event in EVENTS], axis=1)
        for model in MODELS], axis=1)
    # [source, QP, candidate, analyzer, event]
    predicted = predicted.reshape(len(rows), 5, 6, 2, 2)
    if not np.isfinite(predicted).all() or np.any((predicted < 0) | (predicted > 1)):
        raise ValueError("invalid V6 event probabilities")
    prepared = []
    for source_index, video in enumerate(raw):
        prepared_video = []
        for qp_index, (measurement, obs, base) in enumerate(video):
            probabilities = predicted[source_index, qp_index].copy()
            probabilities[base] = 0.0
            prepared_video.append((measurement, obs, base, probabilities))
        prepared.append(prepared_video)
    return prepared


def select_residual(obs: list[dict], base: int, probabilities: np.ndarray,
                    policy: dict) -> int:
    if (policy.get("mode") != "V6" or base not in range(len(obs))
            or probabilities.shape != (len(obs), 2, 2)
            or not np.isfinite(probabilities).all()
            or np.any((probabilities < 0) | (probabilities > 1))):
        raise ValueError("invalid V6 selection inputs")
    threshold, weight = policy["minimum_expected_delta"], policy["feature_weight"]
    if threshold not in THRESHOLDS or weight not in WEIGHTS:
        raise ValueError("V6 policy is outside preregistered grid")
    admissible = [base]
    for index in range(len(obs)):
        if index == base:
            continue
        expected = probabilities[index, :, 1] - probabilities[index, :, 0]
        if np.all(expected >= threshold):
            admissible.append(index)

    def score(index: int) -> tuple[float, int]:
        distance = np.mean([obs[index]["signals"][model]["feature_distance"]
                            - obs[base]["signals"][model]["feature_distance"]
                            for model in MODELS])
        value = math.log(obs[index]["bpp"] / obs[base]["bpp"]) + weight * distance
        return value, index

    return min(admissible, key=score)


def selected_arrays_v6(prepared: list, policy: dict | None) -> tuple[np.ndarray, np.ndarray, dict]:
    values, distances, choices = [], [], Counter()
    for video in prepared:
        source_values, source_distances = [], []
        for measurement, obs, base, probabilities in video:
            index = base if policy is None else select_residual(obs, base, probabilities, policy)
            candidate = measurement["candidates"][index]
            source_values.append([candidate["bpp"],
                                  *[float(candidate[field]) for field in FIELDS]])
            source_distances.append([obs[index]["signals"][model]["feature_distance"]
                                     for model in MODELS])
            choices[candidate["name"]] += 1
        values.append(source_values)
        distances.append(source_distances)
    return np.asarray(values), np.asarray(distances), dict(choices)


def is_feasible(report: dict, old_report: dict, distance: float, old_distance: float) -> bool:
    if not np.isfinite(distance) or not np.isfinite(old_distance) or distance >= old_distance:
        return False
    for model in MODELS:
        point, old = report[model]["metrics"], old_report[model]["metrics"]
        rate, old_rate = point["bd_rate_top1_pct"], old["bd_rate_top1_pct"]
        accuracy, gap = point["bd_accuracy_top1"], point["min_same_qp_top1_gap"]
        if (rate is None or old_rate is None or accuracy is None or gap is None
                or not all(np.isfinite(v) for v in (rate, old_rate, accuracy, gap))
                or rate > old_rate + TOLERANCE_PP
                or accuracy <= 0 or gap < MIN_GAP):
            return False
    return True


def calibrate(rows: list[dict], risk: dict, old_policy: dict, models: dict) -> dict:
    prepared = predicted_measurements(rows, risk, old_policy, models)
    base, _ = selected_arrays(prepare(rows, risk), {"mode": "identity"})
    old, old_distance_array, old_choices = selected_arrays_v6(prepared, None)
    old_report = metrics(base, old)
    old_distance = float(old_distance_array.mean())
    grid = []
    for policy in policy_grid():
        trial, distances, choices = selected_arrays_v6(prepared, policy)
        report = metrics(base, trial)
        distance = float(distances.mean())
        feasible = is_feasible(report, old_report, distance, old_distance)
        rates = [report[model]["metrics"]["bd_rate_top1_pct"] for model in MODELS]
        grid.append({"policy": policy, "feasible": feasible,
                     "mean_feature_distance": distance,
                     "mean_feature_distance_delta_vs_v2": distance - old_distance,
                     "worst_bd_rate": max(rates) if feasible else None,
                     "sum_bd_rate": sum(rates) if feasible else None,
                     "analyzers": {model: report[model]["metrics"] for model in MODELS},
                     "choices": choices})
    feasible_rows = [row for row in grid if row["feasible"]]
    chosen = min(feasible_rows, key=lambda row:
                 (row["mean_feature_distance"], row["worst_bd_rate"],
                  row["sum_bd_rate"], row["policy"]["minimum_expected_delta"],
                  row["policy"]["feature_weight"])) if feasible_rows else None
    return {"grid": grid, "selected_policy": chosen["policy"] if chosen else None,
            "selected_calibration_point": chosen if chosen else None,
            "v2_calibration_point": {model: old_report[model]["metrics"] for model in MODELS},
            "v2_mean_feature_distance": old_distance, "v2_choices": old_choices}


def proxy_bootstrap_delta(old: np.ndarray, new: np.ndarray) -> dict:
    paired = (new - old).mean(axis=(1, 2))
    rng = np.random.default_rng(SEED)
    draws = [float(paired[rng.integers(0, len(paired), len(paired))].mean())
             for _ in range(DRAWS)]
    return {"point": float(paired.mean()), "ci95": np.percentile(draws, [2.5, 97.5]).tolist(),
            "valid_draws": DRAWS, "requested_draws": DRAWS}


def evaluate_dev(rows: list[dict], risk: dict, old_policy: dict,
                 models: dict, policy: dict) -> dict:
    prepared = predicted_measurements(rows, risk, old_policy, models)
    base, _ = selected_arrays(prepare(rows, risk), {"mode": "identity"})
    old, old_distances, old_choices = selected_arrays_v6(prepared, None)
    new, new_distances, new_choices = selected_arrays_v6(prepared, policy)
    comparisons = {}
    for name, anchor, trial in (("V2-C_vs_identity", base, old),
                                ("V6_vs_identity", base, new),
                                ("V6_vs_V2-C", old, new)):
        comparisons[name] = {"analyzers": metrics(anchor, trial),
                             "bootstrap": bootstrap(anchor, trial, DRAWS, SEED)}
    go = is_feasible(comparisons["V6_vs_identity"]["analyzers"],
                     comparisons["V2-C_vs_identity"]["analyzers"],
                     float(new_distances.mean()), float(old_distances.mean()))
    return {"comparisons": comparisons,
            "proxy_feature_distance": {"V2-C_mean": float(old_distances.mean()),
                                       "V6_mean": float(new_distances.mean()),
                                       "paired_delta": proxy_bootstrap_delta(old_distances, new_distances)},
            "choices": {"V2-C": old_choices, "V6": new_choices},
            "go_no_go_this_codec": go}


def run(roots: dict[str, Path], out_dir: Path) -> dict:
    code_commit = verify_preregistration()
    if set(roots) != {"h264", "h265"} or out_dir.exists():
        raise ValueError("both codecs required and output directory must be new")
    locked_cache, lock_sha = load_locked_dev_cache()
    loaded = {codec: load_development(roots[codec], codec)
              for codec in ("h264", "h265")}
    verify_loaded_cache(loaded, locked_cache)
    if loaded["h264"][5]["source_fingerprints"] != loaded["h265"][5]["source_fingerprints"]:
        raise ValueError("development source differs by codec")
    reports, fitted_models = {}, {}
    for codec in ("h264", "h265"):
        fit, calibration, dev, risk, old_policy, provenance = loaded[codec]
        models, counts = fit_event_models(fit, risk, old_policy)
        selection = calibrate(calibration, risk, old_policy, models)
        assessment = (evaluate_dev(dev, risk, old_policy, models,
                                   selection["selected_policy"])
                      if selection["selected_policy"] is not None else None)
        fitted_models[codec] = models
        reports[codec] = {
            "experiment": "v6_paired_v2_residual_dev",
            "scope": "FIT/CALIBRATION/DEV only; no mc3, TEST or holdout outcome",
            "codec": codec,
            "preregistration_commit": PREREG_COMMIT,
            "analysis_code_commit": code_commit,
            "sklearn_version": sklearn.__version__,
            "model_params": MODEL_PARAMS,
            "threshold_grid": list(THRESHOLDS),
            "feature_weight_grid": list(WEIGHTS),
            "dev_cache_manifest_sha256": lock_sha,
            "dev_cache_archive_sha256": locked_cache["archive_sha256"],
            "input_provenance": provenance,
            "fit_event_counts": counts,
            "bootstrap_unit": "source video; all QPs, arms and primary analyzers paired",
            "bootstrap_seed": SEED,
            "bootstrap_draws": DRAWS,
            "calibration": selection,
            "dev": assessment,
        }
    out_dir.mkdir(parents=True)
    for codec, report in reports.items():
        model_dir = out_dir / "models" / codec
        model_dir.mkdir(parents=True)
        report["fitted_model_sha256"] = {}
        for analyzer in MODELS:
            report["fitted_model_sha256"][analyzer] = {}
            for event in EVENTS:
                path = model_dir / f"{analyzer}_{event}.joblib"
                joblib.dump(fitted_models[codec][analyzer][event], path, compress=3)
                report["fitted_model_sha256"][analyzer][event] = file_sha256(path)
        path = out_dir / f"{codec}_result.json"
        write_json(path, report)
        path.with_suffix(".sha256").write_text(
            f"{file_sha256(path)}  {path.name}\n", encoding="utf-8")
    return {codec: {"selected": report["calibration"]["selected_policy"] is not None,
                    "go_no_go_this_codec": (report["dev"] or {}).get("go_no_go_this_codec")}
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
