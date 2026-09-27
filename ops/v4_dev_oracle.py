#!/usr/bin/env python
"""Label-aware, non-deployable DEV oracle for six-candidate headroom screening."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

from ops.dual_codec_search import FIELDS, digest, metrics, validate_row, write_json
from ops.v3_dev_policy import EXPECTED_FINGERPRINTS, REPO, file_sha256, source_id

PLAN_COMMIT = "16e7cdf78b85d91328bb60f1237c4768d2a5a6ae"
PILOT_INDEX_SHA256 = "1a7adb6ad3aac2fa3fc93767c9567e49441b35f7ad6375fe7e1949ef0507acb2"


def verify_plan() -> str:
    git = ["git", "-c", f"safe.directory={REPO.as_posix()}"]
    subprocess.run(git + ["merge-base", "--is-ancestor", PLAN_COMMIT, "HEAD"],
                   cwd=REPO, check=True)
    locked = subprocess.check_output(
        git + ["show", f"{PLAN_COMMIT}:docs/V4_DEV_SCREENING_PLAN.md"], cwd=REPO)
    current = (REPO / "docs/V4_DEV_SCREENING_PLAN.md").read_bytes()
    if current.replace(b"\r\n", b"\n") != locked:
        raise ValueError("DEV screen plan changed after its lock commit")
    subprocess.run(git + ["ls-files", "--error-unmatch", "ops/v4_dev_oracle.py"],
                   cwd=REPO, check=True, capture_output=True)
    subprocess.run(git + ["diff", "--quiet", "HEAD", "--", "ops/v4_dev_oracle.py"],
                   cwd=REPO, check=True)
    return subprocess.check_output(git + ["rev-parse", "HEAD"], cwd=REPO,
                                   text=True).strip()


def load_dev(root: Path, codec: str) -> tuple[list[dict], dict]:
    root = root.resolve()
    if root.name != codec or root.parent.name != "dual_codec_search_v2":
        raise ValueError("only original V2 pilot DEV cache is allowed")
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = manifest["split_ids"]["dev"]
    if (manifest.get("experiment") != "dual_codec_search_v2_pilot"
            or manifest.get("codec") != codec
            or manifest.get("split_fingerprints") != EXPECTED_FINGERPRINTS
            or len(ids) != 200 or len(set(ids)) != 200
            or len({source_id(key) for key in ids}) != 200):
        raise ValueError("DEV manifest differs from preregistered pilot")
    files = sorted((root / "cache" / "dev").glob("clip_*.json"))
    if len(files) != 200:
        raise ValueError("DEV cache must have exactly 200 records")
    by_id = {}
    tree = hashlib.sha256()
    for path in files:
        row = json.loads(path.read_text(encoding="utf-8"))
        key = row["sequence_id"]
        if key in by_id:
            raise ValueError("duplicate DEV source")
        validate_row(row, key, codec, digest(manifest))
        by_id[key] = row
        tree.update(f"{path.name}\t{file_sha256(path)}\n".encode())
    if set(by_id) != set(ids):
        raise ValueError("DEV records differ from pilot manifest")
    return [by_id[key] for key in ids], {
        "pilot_manifest_sha256": file_sha256(manifest_path),
        "pilot_index_sha256": PILOT_INDEX_SHA256,
        "dev_cache_tree_sha256": tree.hexdigest(),
        "dev_source_fingerprint": EXPECTED_FINGERPRINTS["dev"]}


def oracle_choice(measurement: dict) -> tuple[int, bool, bool]:
    """Use truth only for a DEV upper reference; never deploy this selector."""
    candidates = measurement["candidates"]
    anchor = candidates[0]
    feasible = [index for index, row in enumerate(candidates)
                if all(not anchor[field] or row[field] for field in FIELDS)]
    if 0 not in feasible:
        raise ValueError("identity must be a feasible oracle action")
    selected = min(feasible, key=lambda index: candidates[index]["bpp"])
    nonidentity = any(index > 0 for index in feasible)
    saving = any(index > 0 and candidates[index]["bpp"] < anchor["bpp"]
                 for index in feasible)
    return selected, nonidentity, saving


def evaluate(rows: list[dict]) -> dict:
    identity, oracle = [], []
    choices = Counter()
    nonidentity = saving = 0
    for row in rows:
        base_video, oracle_video = [], []
        for measurement in row["measurements"]:
            anchor = measurement["candidates"][0]
            index, has_nonidentity, has_saving = oracle_choice(measurement)
            chosen = measurement["candidates"][index]
            base_video.append([anchor["bpp"], *[float(anchor[field]) for field in FIELDS]])
            oracle_video.append([chosen["bpp"], *[float(chosen[field]) for field in FIELDS]])
            choices[chosen["name"]] += 1
            nonidentity += has_nonidentity
            saving += has_saving
        identity.append(base_video)
        oracle.append(oracle_video)
    identity = np.asarray(identity)
    oracle = np.asarray(oracle)
    if len(identity) != 200 or identity.shape != oracle.shape or identity.shape[1:] != (5, 3):
        raise ValueError("unexpected DEV array shape")
    return {"n": len(rows), "n_video_qp": len(rows) * 5,
            "nonidentity_feasible_rows": nonidentity,
            "rate_saving_feasible_rows": saving,
            "nonidentity_feasible_fraction": nonidentity / (len(rows) * 5),
            "rate_saving_feasible_fraction": saving / (len(rows) * 5),
            "choices": dict(choices), "analyzers": metrics(identity, oracle),
            "interpretation": "Label-aware optimistic DEV reference; not a deployable policy."}


def run(roots: dict[str, Path], out_dir: Path) -> dict:
    code_commit = verify_plan()
    if set(roots) != {"h264", "h265"}:
        raise ValueError("both codecs required")
    reports = {}
    for codec in ("h264", "h265"):
        rows, provenance = load_dev(roots[codec], codec)
        reports[codec] = {"experiment": "v4_dev_oracle_screen",
            "codec": codec, "plan_commit": PLAN_COMMIT,
            "analysis_code_commit": code_commit, "input_provenance": provenance,
            "bootstrap_unit": "source video; point estimate only",
            "bootstrap_seed": None, "bootstrap_draws": 0,
            **evaluate(rows)}
    out_dir.mkdir(parents=True, exist_ok=True)
    for codec, report in reports.items():
        path = out_dir / f"{codec}_result.json"
        if path.exists():
            raise FileExistsError(f"refusing to overwrite DEV screen: {path}")
        write_json(path, report)
        path.with_suffix(".sha256").write_text(
            f"{file_sha256(path)}  {path.name}\n", encoding="utf-8")
    return {codec: {"bd_rate": {model: data["metrics"]["bd_rate_top1_pct"]
                                for model, data in report["analyzers"].items()},
                    "rate_saving_feasible_fraction": report["rate_saving_feasible_fraction"]}
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
