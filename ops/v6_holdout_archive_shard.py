#!/usr/bin/env python
"""Stream a bounded subset of official K400 archives for V6 byte-only preflight.

No annotation, label, codec or analyzer is loaded. Different Kaggle accounts
may process disjoint archive-number ranges; the returned bytes are combined
locally before the 1,000-source ID lock.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from ops.prepare_official_holdout import REPO, archive_part, archive_urls, sha256
from ops.prepare_v6_holdout import (ARCHIVE_PATHS_SHA256, AUDIT_REL,
                                    v2_holdout_ids, v4_holdout_ids)

PLAN = REPO / AUDIT_REL / "candidate_plan.json"
IDS = REPO / AUDIT_REL / "candidate_ids.txt"
URLS = REPO / "configs/holdout_source_audit/official_val_archive_paths.txt"
PRIOR_PARTS = REPO / "configs/holdout_source_audit/archive_parts"


def committed_bytes(relative: str, path: Path) -> bytes:
    blob = subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", "show",
         f"HEAD:{relative}"], cwd=REPO)
    if blob != path.read_bytes().replace(b"\r\n", b"\n"):
        raise ValueError(f"source lock differs from Git: {relative}")
    return blob


def locked_inputs() -> tuple[dict, list[str], list[str]]:
    plan = json.loads(committed_bytes(f"{AUDIT_REL}/candidate_plan.json", PLAN))
    ids = committed_bytes(f"{AUDIT_REL}/candidate_ids.txt", IDS).decode().splitlines()
    if (plan["status"] != "metadata_only" or plan["candidate_limit"] != 2000
            or len(ids) != 2000 or len(set(ids)) != 2000
            or set(ids) & (v2_holdout_ids() | v4_holdout_ids())):
        raise ValueError("invalid V6 candidate ID lock")
    if (sha256(URLS) != ARCHIVE_PATHS_SHA256
            or plan["archive_path_list_sha256"] != ARCHIVE_PATHS_SHA256):
        raise ValueError("official archive URL list changed")
    return plan, ids, archive_urls(URLS)


def run(start: int, stop: int, out_dir: Path) -> dict:
    if not (0 <= start < stop <= 20):
        raise ValueError("archive range must lie within 0..20")
    plan, ids, urls = locked_inputs()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError("archive shard output must be new")
    (out_dir / "parts").mkdir(parents=True, exist_ok=True)
    candidate_set = set(ids)
    parts = []
    for number in range(start, stop):
        _, result = archive_part(number, urls[number], candidate_set, out_dir)
        prior = json.loads((PRIOR_PARTS / f"part_{number:02d}.json").read_text())
        if (result["url"] != prior["url"]
                or result["compressed_sha256"] != prior["compressed_sha256"]
                or result["members_seen"] != prior["members_seen"]):
            raise ValueError(f"official archive {number} differs from V2 audit")
        parts.append({"number": number,
                      "manifest_sha256": sha256(out_dir / "parts" /
                                                f"part_{number:02d}.json"),
                      "compressed_sha256": result["compressed_sha256"],
                      "retained_count": len(result["retained"])})
        print(f"[V6 byte preflight] archive {number+1}/20 retained="
              f"{len(result['retained'])}", flush=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     text=True).strip()
    manifest = {"experiment": "v6_h265_byte_only_preflight",
                "code_commit": commit, "candidate_plan_sha256": sha256(PLAN),
                "candidate_ids_sha256": sha256(IDS),
                "candidate_ids_fingerprint": plan["candidate_ids_fingerprint"],
                "part_start": start, "part_stop": stop, "parts": parts,
                "scope": "source ID and video bytes only; no labels or analyzer outcomes"}
    (out_dir / "shard_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--stop", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.start, args.stop, args.out_dir)), flush=True)


if __name__ == "__main__":
    main()
