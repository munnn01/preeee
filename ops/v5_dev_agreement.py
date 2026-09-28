#!/usr/bin/env python
"""Preregistered V5 agreement-guard screen on FIT/CALIBRATION/DEV only."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

import joblib
import numpy as np

from ops.dual_codec_search import FIELDS, bootstrap, metrics, prepare, selected_arrays, write_json
from ops.v3_dev_policy import REPO, file_sha256
from ops.v4_dev_policy import (load_development, policy_grid,
                               predicted_measurements, selected_arrays_v4,
                               threshold_tuple)
from src.models.dual_codec_search import MODELS

PREREG_COMMIT = "bca2f7ce26c8b741c124d878a714495b4897c789"
FROZEN_MANIFEST_SHA256 = "c59d6e4fa4e7837e9f86cd418af0b1c1afcd75adae490ae4e8b3bc3eed45f06f"
SEED = 20260929
DRAWS = 2000
TOLERANCE_PP = 1.0
MIN_GAP = -0.01


def verify_preregistration() -> str:
    git = ["git", "-c", f"safe.directory={REPO.as_posix()}"]
    subprocess.run(git + ["merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD"],
                   cwd=REPO, check=True)
    locked = subprocess.check_output(
        git + ["show", f"{PREREG_COMMIT}:docs/PREREGISTRATION_V5.md"], cwd=REPO)
    current = (REPO / "docs/PREREGISTRATION_V5.md").read_bytes()
    if current.replace(b"\r\n", b"\n") != locked:
        raise ValueError("V5 preregistration changed after lock")
    subprocess.run(git + ["ls-files", "--error-unmatch", "ops/v5_dev_agreement.py"],
                   cwd=REPO, check=True, capture_output=True)
    subprocess.run(git + ["diff", "--quiet", "HEAD", "--", "ops/v5_dev_agreement.py"],
                   cwd=REPO, check=True)
    return subprocess.check_output(git + ["rev-parse", "HEAD"], cwd=REPO,
                                   text=True).strip()


def load_frozen_v4() -> tuple[dict, str]:
    path = REPO / "configs/v4_frozen/manifest.json"
    digest = file_sha256(path)
    if digest != FROZEN_MANIFEST_SHA256:
        raise ValueError("V4 frozen manifest SHA-256 changed")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (manifest.get("experiment") != "v4_correctness_selector_frozen_before_new_holdout"
            or set(manifest.get("codecs", {})) != {"h264", "h265"}):
        raise ValueError("unexpected frozen V4 manifest")
    return manifest, digest


def load_models(codec: str, manifest: dict) -> tuple[dict, dict]:
    entry = manifest["codecs"][codec]
    models, hashes = {}, {}
    for model in MODELS:
        path = REPO / entry["model_paths"][model]
        actual = file_sha256(path)
        if actual != entry["model_sha256"][model]:
            raise ValueError(f"frozen {codec} {model} model changed")
        models[model] = joblib.load(path)
        if list(models[model].classes_) != [0, 1]:
            raise ValueError("frozen correctness class order changed")
        hashes[model] = actual
    return models, hashes


def select_guarded(obs: list[dict], probabilities: np.ndarray,
                   qp: int, policy: dict) -> int:
    if policy.get("mode") != "P4" or probabilities.shape != (len(obs), len(MODELS)):
        raise ValueError("V5 requires a P4 threshold tuple and two probability models")
    if not np.isfinite(probabilities).all():
        raise ValueError("non-finite correctness probability")
    limits = policy["thresholds_low"] if qp <= 35 else policy["thresholds_high"]
    feasible = [0]
    for index, candidate in enumerate(obs[1:], 1):
        if candidate["bpp"] >= obs[0]["bpp"]:
            continue
        if not all(candidate["signals"][model]["anchor_top1_agrees"] for model in MODELS):
            continue
        if all(probabilities[index, j] - probabilities[0, j] >= limits[model]
               for j, model in enumerate(MODELS)):
            feasible.append(index)
    return min(feasible, key=lambda index: obs[index]["bpp"])


def selected_arrays_v5(prepared: list, policy: dict) -> tuple[np.ndarray, dict]:
    values, choices = [], Counter()
    for video in prepared:
        selections = []
        for measurement, obs, probabilities in video:
            index = select_guarded(obs, probabilities, measurement["qp"], policy)
            candidate = measurement["candidates"][index]
            selections.append([candidate["bpp"],
                               *[float(candidate[field]) for field in FIELDS]])
            choices[candidate["name"]] += 1
        values.append(selections)
    return np.asarray(values), dict(choices)


def is_feasible(report: dict, old_report: dict) -> bool:
    for model in MODELS:
        point = report[model]["metrics"]
        old = old_report[model]["metrics"]
        bd_rate = point["bd_rate_top1_pct"]
        if (bd_rate is None or old["bd_rate_top1_pct"] is None
                or not np.isfinite(bd_rate)
                or not np.isfinite(old["bd_rate_top1_pct"])
                or bd_rate > old["bd_rate_top1_pct"] + TOLERANCE_PP
                or point["bd_accuracy_top1"] is None
                or not np.isfinite(point["bd_accuracy_top1"])
                or point["bd_accuracy_top1"] <= 0
                or point["min_same_qp_top1_gap"] is None
                or not np.isfinite(point["min_same_qp_top1_gap"])
                or point["min_same_qp_top1_gap"] < MIN_GAP):
            return False
    return True


def development_arrays(rows: list[dict], risk: dict, old_policy: dict,
                       models: dict, frozen_v4: dict) -> tuple:
    old_prepared = prepare(rows, risk)
    base, _ = selected_arrays(old_prepared, {"mode": "identity"})
    old, old_choices = selected_arrays(old_prepared, old_policy)
    prepared = predicted_measurements(rows, models)
    v4, v4_choices = selected_arrays_v4(prepared, frozen_v4)
    return base, old, v4, prepared, old_choices, v4_choices


def calibrate(rows: list[dict], risk: dict, old_policy: dict,
              models: dict, frozen_v4: dict) -> dict:
    base, old, v4, prepared, old_choices, v4_choices = development_arrays(
        rows, risk, old_policy, models, frozen_v4)
    old_report = metrics(base, old)
    v4_report = metrics(base, v4)
    grid = []
    for policy in policy_grid():
        trial, choices = selected_arrays_v5(prepared, policy)
        report = metrics(base, trial)
        feasible = is_feasible(report, old_report)
        rates = [report[model]["metrics"]["bd_rate_top1_pct"] for model in MODELS]
        grid.append({"policy": policy, "thresholds": threshold_tuple(policy),
                     "feasible": feasible,
                     "worst_bd_rate": max(rates) if feasible else None,
                     "sum_bd_rate": sum(rates) if feasible else None,
                     "analyzers": {model: report[model]["metrics"] for model in MODELS},
                     "choices": choices})
    feasible_rows = [item for item in grid if item["feasible"]]
    chosen = min(feasible_rows, key=lambda item:
                 (item["worst_bd_rate"], item["sum_bd_rate"], item["thresholds"])) \
        if feasible_rows else None
    return {"grid": grid,
            "selected_policy": chosen["policy"] if chosen else None,
            "selected_calibration_point": chosen["analyzers"] if chosen else None,
            "v2_calibration_point": {model: old_report[model]["metrics"] for model in MODELS},
            "v4_calibration_point": {model: v4_report[model]["metrics"] for model in MODELS},
            "v2_choices": old_choices, "v4_choices": v4_choices}


def evaluate_dev(rows: list[dict], risk: dict, old_policy: dict,
                 models: dict, frozen_v4: dict, policy: dict) -> dict:
    base, old, v4, prepared, old_choices, v4_choices = development_arrays(
        rows, risk, old_policy, models, frozen_v4)
    new, new_choices = selected_arrays_v5(prepared, policy)
    comparisons = {}
    for name, anchor, trial in (
        ("V2-C_vs_identity", base, old),
        ("V4_vs_identity", base, v4),
        ("V5_vs_identity", base, new),
        ("V5_vs_V2-C", old, new),
        ("V5_vs_V4", v4, new),
    ):
        comparisons[name] = {"analyzers": metrics(anchor, trial),
                             "bootstrap": bootstrap(anchor, trial, DRAWS, SEED)}
    go = is_feasible(comparisons["V5_vs_identity"]["analyzers"],
                     comparisons["V2-C_vs_identity"]["analyzers"])
    return {"comparisons": comparisons,
            "choices": {"V2-C": old_choices, "V4": v4_choices, "V5": new_choices},
            "go_no_go_this_codec": go}


def run(roots: dict[str, Path], out_dir: Path) -> dict:
    code_commit = verify_preregistration()
    if set(roots) != {"h264", "h265"} or out_dir.exists():
        raise ValueError("both codecs required and output directory must be new")
    frozen, frozen_sha = load_frozen_v4()
    loaded = {codec: load_development(roots[codec], codec)
              for codec in ("h264", "h265")}
    if loaded["h264"][5]["source_fingerprints"] != loaded["h265"][5]["source_fingerprints"]:
        raise ValueError("development source differs by codec")
    reports = {}
    for codec in ("h264", "h265"):
        _fit, calibration, dev, risk, old_policy, provenance = loaded[codec]
        models, model_hashes = load_models(codec, frozen)
        v4_policy = frozen["codecs"][codec]["policy"]
        selection = calibrate(calibration, risk, old_policy, models, v4_policy)
        assessment = (evaluate_dev(dev, risk, old_policy, models,
                                   v4_policy, selection["selected_policy"])
                      if selection["selected_policy"] is not None else None)
        reports[codec] = {
            "experiment": "v5_dev_agreement_guard",
            "scope": "FIT/CALIBRATION/DEV only; no holdout or transfer-analyzer outcome",
            "codec": codec,
            "preregistration_commit": PREREG_COMMIT,
            "analysis_code_commit": code_commit,
            "frozen_v4_manifest_sha256": frozen_sha,
            "frozen_v4_model_sha256": model_hashes,
            "input_provenance": provenance,
            "bootstrap_unit": "source video; all QPs, arms and primary analyzers paired",
            "bootstrap_seed": SEED,
            "bootstrap_draws": DRAWS,
            "calibration": selection,
            "dev": assessment,
        }
    out_dir.mkdir(parents=True)
    for codec, report in reports.items():
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
