#!/usr/bin/env python
"""Preregistered DEV-only search for a per-analyzer V3 risk threshold policy.

Reads only the original pilot FIT/CALIBRATION/DEV caches. The V2 TEST and the
completed V2 holdout results are never opened. A fresh holdout requires its
own later ID lock, policy freeze, and one-shot evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import product
import hashlib
import json
from pathlib import Path
import re
import subprocess

import numpy as np

from ops.dual_codec_search import (FIELDS, bootstrap, digest, eligible, metrics,
                                   prepare, selected_arrays, validate_row, write_json)
from src.models.dual_codec_search import MODELS, passes

REPO = Path(__file__).resolve().parents[1]
PREREG_COMMIT = "245dc868f2be32679042dbe1f8a012a43abac47c"
EXPECTED_FINGERPRINTS = {
    "fit": "4c12443af5c0ef44dc5143217ab00b146e0d9090607c49393487d5decd4e4bb1",
    "calibration": "ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721",
    "dev": "6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258",
}
STAGE_COUNTS = {"fit": 400, "calibration": 200, "dev": 200}
PRIMARY = {"kl": .1, "feature": .05, "confidence": .6}
LOW = (.05, .10, .20)
HIGH = (.10, .20, .30)
BOOTSTRAP_SEED = 20260928
BOOTSTRAP_DRAWS = 2000
SOURCE_RE = re.compile(r"^([A-Za-z0-9_-]{11})(?:_\d+_\d+)?$")


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def source_id(key: str) -> str:
    match = SOURCE_RE.fullmatch(Path(key).stem)
    if match is None:
        raise ValueError(f"cannot identify source video: {key}")
    return match.group(1)


def verify_preregistration() -> str:
    git = ["git", "-c", f"safe.directory={REPO.as_posix()}"]
    subprocess.run(git + ["merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD"],
                   cwd=REPO, check=True)
    frozen = subprocess.check_output(
        git + ["show", f"{PREREG_COMMIT}:docs/PREREGISTRATION_V3.md"], cwd=REPO)
    current = (REPO / "docs/PREREGISTRATION_V3.md").read_bytes()
    if current.replace(b"\r\n", b"\n") != frozen:
        raise ValueError("V3 preregistration changed after its lock commit")
    subprocess.run(git + ["ls-files", "--error-unmatch", "ops/v3_dev_policy.py"],
                   cwd=REPO, check=True, capture_output=True)
    subprocess.run(git + ["diff", "--quiet", "HEAD", "--", "ops/v3_dev_policy.py"],
                   cwd=REPO, check=True)
    return subprocess.check_output(git + ["rev-parse", "HEAD"], cwd=REPO,
                                   text=True).strip()


def policy_grid() -> list[dict]:
    return [{"mode": "C3", "primary": PRIMARY,
             "risk_low": dict(zip(MODELS, (low_r2, low_r3))),
             "risk_high": dict(zip(MODELS, (high_r2, high_r3)))}
            for low_r2, low_r3, high_r2, high_r3
            in product(LOW, LOW, HIGH, HIGH)]


def thresholds(policy: dict) -> tuple[float, float, float, float]:
    return (policy["risk_low"][MODELS[0]], policy["risk_low"][MODELS[1]],
            policy["risk_high"][MODELS[0]], policy["risk_high"][MODELS[1]])


def select_v3(obs: list[dict], qp: int, risks: np.ndarray, policy: dict) -> int:
    if policy.get("mode") != "C3" or risks.shape != (len(obs), len(MODELS)):
        raise ValueError("V3 selection needs observations and paired risk scores")
    limits = policy["risk_low"] if qp <= 35 else policy["risk_high"]
    feasible = [0]
    for index, candidate in enumerate(obs[1:], 1):
        if candidate["bpp"] >= obs[0]["bpp"]:
            continue
        if not passes(candidate, obs[0], MODELS[0], policy["primary"]):
            continue
        if any(not np.isfinite(risks[index, j]) or risks[index, j] > limits[model]
               for j, model in enumerate(MODELS)):
            continue
        feasible.append(index)
    return min(feasible, key=lambda index: obs[index]["bpp"])


def selected_arrays_v3(prepared: list, policy: dict) -> tuple[np.ndarray, dict]:
    if policy["mode"] != "C3":
        return selected_arrays(prepared, policy)
    values, choices = [], Counter()
    for measurements in prepared:
        video = []
        for measurement, obs, risks in measurements:
            index = select_v3(obs, measurement["qp"], risks, policy)
            chosen = measurement["candidates"][index]
            video.append([chosen["bpp"], *[float(chosen[field]) for field in FIELDS]])
            choices[chosen["name"]] += 1
        values.append(video)
    return np.asarray(values), dict(choices)


def load_pilot(root: Path, codec: str, forbidden: set[str]) -> tuple[dict, dict, dict, dict]:
    root = root.resolve()
    if root.name != codec or root.parent.name != "dual_codec_search_v2":
        raise ValueError("only an original V2 pilot cache is allowed")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("experiment") != "dual_codec_search_v2_pilot"
            or manifest.get("codec") != codec
            or manifest.get("split_fingerprints") != EXPECTED_FINGERPRINTS
            or {stage: len(manifest["split_ids"][stage]) for stage in STAGE_COUNTS}
            != STAGE_COUNTS):
        raise ValueError("pilot manifest is not the preregistered DEV source")
    stage_sources = {stage: {source_id(key) for key in manifest["split_ids"][stage]}
                     for stage in STAGE_COUNTS}
    if (any(len(stage_sources[stage]) != STAGE_COUNTS[stage] for stage in STAGE_COUNTS)
            or any(stage_sources[a] & stage_sources[b]
                   for a, b in (("fit", "calibration"), ("fit", "dev"),
                                ("calibration", "dev")))
            or any(values & forbidden for values in stage_sources.values())):
        raise ValueError("DEV source overlap or duplicate")
    state_path = root / "risk_model.json"
    frozen_path = root / "frozen_policy.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    if (frozen["manifest_sha256"] != digest(manifest)
            or frozen["risk_sha256"] != digest(state)
            or frozen["selected_policy"]["mode"] != "C"):
        raise ValueError("original risk model or V2-C policy changed")
    cache_key = digest(manifest)
    stages, hashes = {}, {}
    for stage, count in STAGE_COUNTS.items():
        files = sorted((root / "cache" / stage).glob("clip_*.json"))
        if len(files) != count:
            raise ValueError(f"incomplete {codec} {stage} cache")
        by_id = {}
        tree = hashlib.sha256()
        for path in files:
            row = json.loads(path.read_text(encoding="utf-8"))
            key = row["sequence_id"]
            if key in by_id:
                raise ValueError("duplicate video record")
            validate_row(row, key, codec, cache_key)
            by_id[key] = row
            tree.update(f"{path.name}\t{file_sha256(path)}\n".encode())
        ids = manifest["split_ids"][stage]
        if set(by_id) != set(ids):
            raise ValueError(f"{codec} {stage} IDs differ from frozen manifest")
        stages[stage] = [by_id[key] for key in ids]
        hashes[stage] = tree.hexdigest()
    index_path = root.parents[2] / "kinetics_hash_split.json"
    if not index_path.is_file():
        raise ValueError("original pilot index missing")
    provenance = {"manifest_sha256": file_sha256(manifest_path),
                  "index_sha256": file_sha256(index_path),
                  "risk_model_sha256": file_sha256(state_path),
                  "frozen_policy_sha256": file_sha256(frozen_path),
                  "cache_tree_sha256": hashes,
                  "split_fingerprints": manifest["split_fingerprints"]}
    return state, frozen["selected_policy"], stages, provenance


def point_for(report: dict) -> dict:
    return {model: report[model]["metrics"] for model in MODELS}


def calibrate(rows: list[dict], state: dict, old_policy: dict) -> dict:
    prepared = prepare(rows, state)
    identity, _ = selected_arrays(prepared, {"mode": "identity"})
    old_array, old_choices = selected_arrays(prepared, old_policy)
    old_report = metrics(identity, old_array)
    grid = []
    for policy in policy_grid():
        array, choices = selected_arrays_v3(prepared, policy)
        report = metrics(identity, array)
        okay = eligible(report)
        br = [report[model]["metrics"]["bd_rate_top1_pct"] for model in MODELS]
        grid.append({"policy": policy, "thresholds": thresholds(policy),
                     "eligible": okay, "worst_bd_rate": max(br) if okay else None,
                     "sum_bd_rate": sum(br) if okay else None,
                     "analyzers": point_for(report), "choices": choices})
    feasible = [row for row in grid if row["eligible"]]
    best = min(feasible, key=lambda row: (row["worst_bd_rate"],
               row["sum_bd_rate"], row["thresholds"])) if feasible else None
    old_br = {model: old_report[model]["metrics"]["bd_rate_top1_pct"]
              for model in MODELS}
    if not eligible(old_report) or any(value is None for value in old_br.values()):
        raise ValueError("frozen V2-C calibration comparator is invalid")
    old_worst = max(old_br.values())
    promoted = bool(best is not None and
                    best["worst_bd_rate"] <= old_worst - 1.0 and
                    all(best["analyzers"][model]["bd_rate_top1_pct"] <=
                        old_br[model] + .5 for model in MODELS))
    return {"grid": grid, "best_grid_policy": best["policy"] if best else None,
            "best_grid_point": best["analyzers"] if best else None,
            "old_policy": old_policy, "old_point": point_for(old_report),
            "old_choices": old_choices, "promoted": promoted,
            "selected_policy": best["policy"] if promoted else old_policy}


def evaluate_dev(rows: list[dict], state: dict, old_policy: dict,
                 selection: dict) -> dict:
    prepared = prepare(rows, state)
    identity, _ = selected_arrays(prepared, {"mode": "identity"})
    old, old_choices = selected_arrays(prepared, old_policy)
    new, new_choices = selected_arrays_v3(prepared, selection["selected_policy"])
    comparisons = {}
    for name, anchor, trial in (("V2-C_vs_identity", identity, old),
                                ("V3_vs_identity", identity, new),
                                ("V3_vs_V2-C", old, new)):
        comparisons[name] = {"analyzers": metrics(anchor, trial),
                             "bootstrap": bootstrap(anchor, trial,
                                                    BOOTSTRAP_DRAWS, BOOTSTRAP_SEED)}
    new_point = comparisons["V3_vs_identity"]["analyzers"]
    old_point = comparisons["V2-C_vs_identity"]["analyzers"]
    go = selection["promoted"] and all(
        new_point[model]["metrics"]["bd_rate_top1_pct"] is not None and
        old_point[model]["metrics"]["bd_rate_top1_pct"] is not None and
        new_point[model]["metrics"]["bd_rate_top1_pct"] <
        old_point[model]["metrics"]["bd_rate_top1_pct"] and
        new_point[model]["metrics"]["bd_accuracy_top1"] > 0 and
        new_point[model]["metrics"]["min_same_qp_top1_gap"] >= -.01
        for model in MODELS)
    return {"comparisons": comparisons,
            "choices": {"V2-C": old_choices, "V3": new_choices},
            "go_no_go_this_codec": go}


def run(roots: dict[str, Path], out_dir: Path) -> dict:
    code_commit = verify_preregistration()
    ids = (REPO / "configs/holdout_source_audit/selected_ids.txt").read_text(
        encoding="utf-8").splitlines()
    forbidden = set(ids)
    if len(forbidden) != 1000:
        raise ValueError("V2 holdout ID audit missing")
    loaded = {codec: load_pilot(root, codec, forbidden)
              for codec, root in roots.items()}
    if set(loaded) != {"h264", "h265"}:
        raise ValueError("both codecs required")
    manifest_paths = {codec: root / "manifest.json" for codec, root in roots.items()}
    manifests = {codec: json.loads(path.read_text(encoding="utf-8"))
                 for codec, path in manifest_paths.items()}
    if (manifests["h264"]["split_ids"] != manifests["h265"]["split_ids"]
            or loaded["h264"][3]["index_sha256"] !=
               loaded["h265"][3]["index_sha256"]):
        raise ValueError("DEV source or index differs across codecs")
    reports = {}
    for codec in ("h264", "h265"):
        state, old_policy, stages, provenance = loaded[codec]
        selection = calibrate(stages["calibration"], state, old_policy)
        dev = evaluate_dev(stages["dev"], state, old_policy, selection)
        reports[codec] = {"experiment": "v3_dev_policy_search",
            "scope": "DEV exploration only; old V2 holdout and TEST excluded",
            "codec": codec, "preregistration_commit": PREREG_COMMIT,
            "analysis_code_commit": code_commit,
            "source_fingerprints": EXPECTED_FINGERPRINTS,
            "input_provenance": provenance, "bootstrap_unit":
            "source video; all QPs, arms and analyzers paired",
            "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_draws": BOOTSTRAP_DRAWS,
            "selection": selection, "dev": dev}
    out_dir.mkdir(parents=True, exist_ok=True)
    for codec, report in reports.items():
        path = out_dir / f"{codec}_result.json"
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing DEV result: {path}")
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
    summary = run({"h264": args.h264_cache_root,
                   "h265": args.h265_cache_root}, args.out_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
