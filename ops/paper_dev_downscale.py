#!/usr/bin/env python
"""Fixed downscaling controls versus frozen V2-C on the old DEV cache only.

This reads the original V2 pilot's VAL/DEV candidate records. It never uses
TEST or a new holdout to select a comparator or change the policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from ops.dual_codec_search import (bootstrap, digest, metrics, prepare,
                                   selected_arrays, validate_row, write_json)
from ops.dual_codec_search_confirm_1000 import CONFIG, load_frozen
from ops.paper_validation import fixed_arrays

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP_SEED = 20260924  # unchanged default in ops.dual_codec_search.bootstrap
BASELINES = ("area96", "area112")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dev(pilot_dir: Path, codec: str, config: dict) -> tuple[list[dict], dict]:
    manifest_path = pilot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("experiment") != "dual_codec_search_v2_pilot"
            or manifest.get("codec") != codec
            or manifest.get("code_commit") != config["pilot_code_commit"]
            or manifest.get("qps") != config["qps"]
            or manifest.get("candidates") != config["candidates"]
            or manifest.get("models") != config["models"]):
        raise ValueError("pilot manifest does not match frozen V2 design")
    ids = manifest["split_ids"]["dev"]
    if (len(ids) != 200 or len(set(ids)) != 200
            or digest(ids) != manifest["split_fingerprints"]["dev"]):
        raise ValueError("DEV IDs or fingerprint changed")
    cache_paths = sorted((pilot_dir / "cache" / "dev").glob("clip_*.json"))
    if len(cache_paths) != 200:
        raise ValueError("incomplete DEV cache")
    by_id = {}
    for path in cache_paths:
        row = json.loads(path.read_text(encoding="utf-8"))
        key = row["sequence_id"]
        if key in by_id:
            raise ValueError("duplicate DEV source ID")
        by_id[key] = row
    if set(by_id) != set(ids):
        raise ValueError("DEV cache and pilot manifest disagree")
    cache_key = digest(manifest)
    rows = [by_id[key] for key in ids]
    for row, key in zip(rows, ids):
        validate_row(row, key, codec, cache_key)
    risk, frozen, policy = load_frozen(codec, config)
    if (json.loads((pilot_dir / "risk_model.json").read_text(encoding="utf-8")) != risk
            or json.loads((pilot_dir / "frozen_policy.json").read_text(
                encoding="utf-8")) != frozen
            or policy != frozen["policies"]["C"]):
        raise ValueError("pilot policy/risk differs from checked-in V2-C")
    provenance = {"pilot_manifest_sha256": sha256(manifest_path),
                  "pilot_code_commit": manifest["code_commit"],
                  "dev_fingerprint": manifest["split_fingerprints"]["dev"],
                  "cache_tree_sha256": hashlib.sha256("".join(
                      f"{path.name}\0{sha256(path)}\n" for path in cache_paths
                  ).encode()).hexdigest(),
                  "frozen_policy_sha256": config["pilot_artifacts"][codec]
                  ["frozen_policy_sha256"],
                  "risk_model_sha256": config["pilot_artifacts"][codec]
                  ["risk_model_sha256"]}
    return rows, provenance


def analyze(rows: list[dict], codec: str, draws: int) -> dict:
    if draws < 1:
        raise ValueError("bootstrap draws must be positive")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    risk, frozen, policy = load_frozen(codec, config)
    prepared = prepare(rows, risk)
    identity, identity_choices = selected_arrays(prepared, {"mode": "identity"})
    selected, selected_choices = selected_arrays(prepared, policy)
    arms = {"V2-C": (selected, selected_choices)}
    for name in BASELINES:
        arms[name] = fixed_arrays(rows, name)
    against_identity = {}
    for name, (array, choices) in arms.items():
        against_identity[name] = {"choices": choices,
                                  "analyzers": metrics(identity, array),
                                  "bootstrap": bootstrap(identity, array, draws)}
    direct = {}
    for name in BASELINES:
        array, _ = arms[name]
        direct[f"V2-C_vs_{name}"] = {"analyzers": metrics(array, selected),
                                    "bootstrap": bootstrap(array, selected, draws)}
    return {"scope": "exploratory paired comparison on old V2 VAL/DEV",
            "codec": codec, "n": len(rows), "qps": config["qps"],
            "bootstrap_draws": draws, "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_unit": "source video; all QPs and arms paired",
            "identity_choices": identity_choices,
            "arms_vs_identity": against_identity,
            "direct_comparisons": direct}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-dir", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--codec", choices=("h264", "h265"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    rows, provenance = load_dev(args.pilot_dir, args.codec, config)
    report = analyze(rows, args.codec, args.bootstrap)
    report["provenance"] = {**provenance,
        "source_archive_sha256": sha256(args.source_archive),
        "index_sha256": sha256(args.index),
        "config_sha256_lf": hashlib.sha256(CONFIG.read_bytes().replace(
            b"\r\n", b"\n")).hexdigest(),
        "analysis_code_commit": subprocess.check_output(
            ["git", "-c", f"safe.directory={REPO.as_posix()}",
             "rev-parse", "HEAD"], cwd=REPO, text=True).strip()}
    write_json(args.out, report)
    print(f"[{args.codec}] DEV n={len(rows)}; wrote {args.out}")


if __name__ == "__main__":
    main()
