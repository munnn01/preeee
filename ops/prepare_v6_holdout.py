#!/usr/bin/env python
"""ID-only V6 source audit and video-byte preflight, before labels/index.

The hash salt and exclusion rule are fixed in PREREGISTRATION_V6_HOLDOUT.md. This
command never loads a classifier, candidate outcome, or Kinetics label. It
streams the same official CVDF validation archives used for V2, retaining only
new hash-ranked candidate source IDs.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
from pathlib import Path
import subprocess

from ops.dual_codec_search import digest
from ops.prepare_official_holdout import (REPO, SOURCE_RE, archive_part,
                                          archive_urls, id_fingerprint,
                                          load_exclusion, preflight, sha256)
from ops.v3_dev_policy import EXPECTED_FINGERPRINTS, source_id

SALT = "v6-h265-holdout-20260928"
ANNOTATION_SHA256 = "358eaf47e7f80ebf9b17d49eb0635ad5e0fdab98a9cbd75ffdd2ee5d5e5b6944"
ARCHIVE_PATHS_SHA256 = "7c75bab47da18ba747e8bdd826bec9139672336fd3431caa71ff563473080e77"
V2_IDS = REPO / "configs/holdout_source_audit/selected_ids.txt"
V2_IDS_SHA256 = "7f4d583812cd0bc20335aeaf2f62520ad8a9c32aa8c3f7d591df39c2a1852bc4"
V4_IDS = REPO / "configs/v4_holdout_source_audit/selected_ids.txt"
V4_IDS_SHA256 = "db5918598a0891094ab190e6c44c34377dc84d6852303e9ceb7dc8938295b223"
FIT_MANIFEST_SHA256 = "c0d1b50d941c790803e1281a5634058f165aa7329ac2849825559635e17d6e67"
AUDIT_REL = "configs/v6_holdout_source_audit"


def official_ids(annotation: Path) -> list[str]:
    if sha256(annotation) != ANNOTATION_SHA256:
        raise ValueError("official annotation bytes differ from locked V6 source")
    with annotation.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        if "youtube_id" not in header:
            raise ValueError("official source-ID field missing")
        column = header.index("youtube_id")
        ids = [row[column] for row in reader]
    if (len(ids) != 19906 or len(set(ids)) != len(ids)
            or any(not SOURCE_RE.fullmatch(key) for key in ids)):
        raise ValueError("official K400 validation IDs changed")
    return ids


def development_ids(manifest_path: Path) -> set[str]:
    if sha256(manifest_path) != FIT_MANIFEST_SHA256:
        raise ValueError("pilot development manifest bytes changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("experiment") != "dual_codec_search_v2_pilot"
            or manifest.get("split_fingerprints") != EXPECTED_FINGERPRINTS):
        raise ValueError("pilot development manifest identity changed")
    ids = set()
    for stage, count in (("fit", 400), ("calibration", 200), ("dev", 200)):
        rows = manifest["split_ids"][stage]
        stage_ids = {source_id(key) for key in rows}
        if (len(rows) != count or len(stage_ids) != count
                or digest(rows) != EXPECTED_FINGERPRINTS[stage]
                or any(not SOURCE_RE.fullmatch(key) for key in stage_ids)
                or ids & stage_ids):
            raise ValueError("pilot development source IDs changed or overlap")
        ids |= stage_ids
    return ids


def locked_holdout_ids(path: Path, expected_sha256: str) -> set[str]:
    if sha256(path) != expected_sha256:
        raise ValueError("prior holdout source lock bytes changed")
    ids = path.read_text(encoding="utf-8").splitlines()
    if (len(ids) != 1000 or len(set(ids)) != 1000
            or any(not SOURCE_RE.fullmatch(key) for key in ids)):
        raise ValueError("prior holdout source IDs changed")
    return set(ids)


def v2_holdout_ids() -> set[str]:
    return locked_holdout_ids(V2_IDS, V2_IDS_SHA256)


def v4_holdout_ids() -> set[str]:
    return locked_holdout_ids(V4_IDS, V4_IDS_SHA256)


def rank_source_ids(official: list[str], exclusions: set[str]) -> list[str]:
    return sorted(set(official) - exclusions,
                  key=lambda key: (hashlib.sha256(
                      f"{SALT}\0{key}".encode()).hexdigest(), key))


def plan(annotation: Path, archive_paths: Path, legacy: list[Path],
         dev_manifest: Path, candidate_limit: int = 2000) -> tuple[dict, list[str]]:
    if candidate_limit != 2000:
        raise ValueError("V6 candidate limit is fixed at 2,000")
    official = official_ids(annotation)
    if sha256(archive_paths) != ARCHIVE_PATHS_SHA256:
        raise ValueError("official archive path list changed")
    archive_urls(archive_paths)
    dev = development_ids(dev_manifest)
    v2 = v2_holdout_ids()
    v4 = v4_holdout_ids()
    historical = set().union(*(load_exclusion(path) for path in legacy))
    exclusions = historical | dev | v2 | v4
    ranked = rank_source_ids(official, exclusions)
    if len(ranked) < candidate_limit or any(key in exclusions for key in ranked):
        raise ValueError("not enough disjoint official source IDs")
    code_commit = subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", "rev-parse", "HEAD"],
        cwd=REPO, text=True).strip()
    audit = {
        "status": "metadata_only", "source": "official CVDF Kinetics-400 validation",
        "salt": SALT, "annotation_sha256": sha256(annotation),
        "archive_path_list_sha256": sha256(archive_paths),
        "legacy_inventories": [{"path": path.name, "sha256": sha256(path)}
                               for path in legacy],
        "development_manifest_sha256": sha256(dev_manifest),
        "development_source_count": len(dev),
        "development_source_fingerprints": EXPECTED_FINGERPRINTS,
        "v2_holdout_ids_sha256": sha256(V2_IDS),
        "v2_holdout_source_count": len(v2),
        "v4_holdout_ids_sha256": sha256(V4_IDS),
        "v4_holdout_source_count": len(v4),
        "official_source_count": len(official),
        "historical_source_count": len(historical),
        "official_historical_overlap": len(set(official) & historical),
        "official_development_overlap": len(set(official) & dev),
        "official_v2_holdout_overlap": len(set(official) & v2),
        "official_v4_holdout_overlap": len(set(official) & v4),
        "eligible_source_count": len(ranked),
        "eligible_source_fingerprint": id_fingerprint(ranked),
        "candidate_limit": candidate_limit, "target": 1000,
        "candidate_ids_fingerprint": id_fingerprint(ranked[:candidate_limit]),
        "code_commit": code_commit,
    }
    return audit, ranked[:candidate_limit]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--archive-paths", type=Path, required=True)
    parser.add_argument("--exclude-inventory", type=Path, action="append", required=True)
    parser.add_argument("--dev-manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        raise ValueError("workers must be 1..8")
    audit, candidates = plan(args.annotation, args.archive_paths,
                             args.exclude_inventory, args.dev_manifest)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.out_dir / "candidate_plan.json"
    ids_path = args.out_dir / "candidate_ids.txt"
    if args.download:
        # The metadata choice must have been committed before any video bytes
        # are streamed. Do not rewrite the plan with a later code commit.
        locked = json.loads(plan_path.read_text(encoding="utf-8"))
        without_commit = {k: v for k, v in audit.items() if k != "code_commit"}
        if ({k: v for k, v in locked.items() if k != "code_commit"}
                != without_commit or ids_path.read_text(encoding="utf-8").splitlines()
                != candidates):
            raise ValueError("V6 ID-only candidate plan changed")
        for name, path in (("candidate_plan.json", plan_path),
                           ("candidate_ids.txt", ids_path)):
            committed = subprocess.check_output(
                ["git", "-c", f"safe.directory={REPO.as_posix()}",
                 "show", f"HEAD:{AUDIT_REL}/{name}"], cwd=REPO)
            if committed != path.read_bytes():
                raise ValueError(f"V6 candidate plan not committed: {name}")
        audit = locked
    else:
        if plan_path.exists() or ids_path.exists():
            raise ValueError("metadata plan output must be new")
        plan_path.write_text(json.dumps(audit, indent=2) + "\n",
                             encoding="utf-8", newline="\n")
        ids_path.write_text("\n".join(candidates) + "\n",
                            encoding="utf-8", newline="\n")
    print(json.dumps({"eligible": audit["eligible_source_count"],
                      "candidates": len(candidates),
                      "prior_holdout_overlap": len(set(candidates) &
                                                    (v2_holdout_ids() | v4_holdout_ids()))}))
    if not args.download:
        return
    (args.out_dir / "parts").mkdir(exist_ok=True)
    urls = archive_urls(args.archive_paths)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(archive_part, number, url, set(candidates),
                                   args.out_dir) for number, url in enumerate(urls)]
        for future in as_completed(futures):
            number, result = future.result()
            print(f"[V6 source preflight] archive {number+1}/20 "
                  f"retained={len(result['retained'])}", flush=True)
    selected = preflight(candidates, 2000, 1000, args.out_dir)
    (args.out_dir / "preflight_selection.json").write_text(
        json.dumps({**audit, **selected, "status": "preflight"}, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    if not selected["complete"]:
        raise RuntimeError("CHƯA ĐO: fewer than 1,000 valid new sources")
    print(json.dumps({"selected": len(selected["selected"]),
                      "fingerprint": selected["selected_source_fingerprint"]}))


if __name__ == "__main__":
    main()
