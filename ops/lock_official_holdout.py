#!/usr/bin/env python
"""Lock ID-only official K400 validation selection before reading its labels.

Two commands are intentionally separate. ``ids`` consumes only source IDs and
video byte hashes; commit its outputs. ``index`` refuses to read the label CSV
until those exact outputs exist in an ancestor Git commit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

from ops.prepare_official_holdout import (REPO, SOURCE_RE, SALT, id_fingerprint,
                                          load_exclusion, ranked_ids, sha256)

MEMBER_RE = re.compile(r"^([A-Za-z0-9_-]{11})_(\d{6})_(\d{6})\.mp4$")
IDS_REL = "configs/holdout_source_audit/selected_ids.txt"
SOURCES_REL = "configs/holdout_source_audit/selected_sources.json"


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", *args], cwd=REPO)


def selection_rows(selection_path: Path, annotation_path: Path,
                   exclusions: list[Path], videos: Path) -> tuple[dict, list[dict]]:
    """Verify the preflight's complete, hash-ranked ID choice without labels."""
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("annotation_sha256") != sha256(annotation_path):
        raise ValueError("annotation bytes differ from preflight")
    if selection.get("target") != 1000 or selection.get("candidate_limit") != 2000:
        raise ValueError("holdout target/candidate limit changed")
    excluded = set().union(*(load_exclusion(p) for p in exclusions))
    ranked, audit = ranked_ids(annotation_path, excluded)
    if (selection.get("source_audit") != audit
            or selection.get("candidate_ids_sha256") != id_fingerprint(ranked[:2000])):
        raise ValueError("ID-only source audit changed")
    rows = selection.get("selected")
    failures = selection.get("failures_before_target")
    if (selection.get("complete") is not True or not isinstance(rows, list)
            or len(rows) != 1000 or not isinstance(failures, list)):
        raise ValueError("preflight has not produced 1,000 selected videos")
    ids = [row["source_id"] for row in rows]
    if (len(set(ids)) != 1000 or any(not SOURCE_RE.fullmatch(key) for key in ids)
            or selection.get("selected_source_fingerprint") != id_fingerprint(ids)):
        raise ValueError("selected source fingerprint or IDs changed")
    failed_ids = [row["source_id"] for row in failures]
    if (len(set(failed_ids)) != len(failed_ids) or set(ids) & set(failed_ids)
            or any(row.get("reason") not in
                   {"missing", "multiple_clips", "undecodable"} for row in failures)):
        raise ValueError("preflight failure list invalid")
    prefix = ranked[:ranked.index(ids[-1]) + 1]
    if (set(prefix) != set(ids) | set(failed_ids)
            or [key for key in prefix if key not in set(failed_ids)] != ids):
        raise ValueError("selection deviates from locked hash rank")
    for row in rows:
        filename = row["filename"]
        match = MEMBER_RE.fullmatch(filename)
        path = videos / filename
        if (match is None or match.group(1) != row["source_id"]
                or not path.is_file() or path.stat().st_size != row["bytes"]
                or sha256(path) != row["video_sha256"]):
            raise ValueError(f"missing, changed or misnamed video: {filename}")
    return selection, rows


def lock_ids(selection_path: Path, annotation_path: Path,
             exclusions: list[Path], videos: Path,
             ids_out: Path, sources_out: Path) -> None:
    selection, rows = selection_rows(selection_path, annotation_path,
                                    exclusions, videos)
    ids_out.parent.mkdir(parents=True, exist_ok=True)
    ids_out.write_text("\n".join(row["source_id"] for row in rows) + "\n",
                       encoding="utf-8", newline="\n")
    sources = {"source": selection["source"], "salt": SALT,
               "target": 1000, "candidate_limit": 2000,
               "annotation_sha256": selection["annotation_sha256"],
               "archive_path_list_sha256": selection["archive_path_list_sha256"],
               "selected_source_fingerprint": selection["selected_source_fingerprint"],
               "selected_ids_sha256": sha256(ids_out),
               "preflight_code_commit": selection["code_commit"],
               "preflight_selection_sha256": sha256(selection_path),
               "failures_before_target": selection["failures_before_target"],
               "selected": rows}
    sources_out.write_text(json.dumps(sources, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    print(json.dumps({"selected": len(rows), "fingerprint":
                      sources["selected_source_fingerprint"],
                      "ids_sha256": sources["selected_ids_sha256"],
                      "sources_sha256": sha256(sources_out)}))


def committed_lock(lock_commit: str, ids_path: Path,
                   sources_path: Path) -> tuple[list[str], dict]:
    """Require the exact ID and source-byte manifest in an ancestor commit."""
    if not re.fullmatch(r"[0-9a-f]{40}", lock_commit):
        raise ValueError("lock commit must be a full SHA-1")
    subprocess.run(["git", "-c", f"safe.directory={REPO.as_posix()}",
                    "merge-base", "--is-ancestor", lock_commit, "HEAD"],
                   cwd=REPO, check=True)
    for relative, path in ((IDS_REL, ids_path), (SOURCES_REL, sources_path)):
        if git("show", f"{lock_commit}:{relative}") != path.read_bytes():
            raise ValueError(f"lock file differs from commit: {relative}")
    ids = ids_path.read_text(encoding="utf-8").splitlines()
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    if (len(ids) != 1000 or len(set(ids)) != 1000
            or sources["selected_ids_sha256"] != sha256(ids_path)
            or sources["selected_source_fingerprint"] != id_fingerprint(ids)
            or [row["source_id"] for row in sources["selected"]] != ids):
        raise ValueError("committed ID lock invalid")
    return ids, sources


def build_index(lock_commit: str, ids_path: Path, sources_path: Path,
                annotation_path: Path, videos: Path, out_path: Path) -> None:
    ids, sources = committed_lock(lock_commit, ids_path, sources_path)
    if sha256(annotation_path) != sources["annotation_sha256"]:
        raise ValueError("annotation bytes differ from committed lock")
    # Labels are read only after committed_lock has succeeded.
    with annotation_path.open(encoding="utf-8", newline="") as stream:
        annotations = {row["youtube_id"]: row for row in csv.DictReader(stream)}
    from src.tasks.action_recognition import kinetics_category_index

    class_maps = [kinetics_category_index(name) for name in
                  ("r2plus1d_18", "r3d_18", "mc3_18")]
    if class_maps[0] != class_maps[1] or class_maps[0] != class_maps[2]:
        raise ValueError("three TorchVision analyzer label orders differ")
    records = []
    for source in sources["selected"]:
        source_id = source["source_id"]
        annotation = annotations[source_id]
        label_name = annotation["label"]
        canonical = re.sub(r"[^a-z0-9]+", " ", label_name.lower()).strip()
        if canonical not in class_maps[0]:
            raise ValueError(f"unmapped Kinetics label: {label_name}")
        match = MEMBER_RE.fullmatch(source["filename"])
        if (match is None or match.group(1) != source_id
                or int(match.group(2)) != int(annotation["time_start"])
                or int(match.group(3)) != int(annotation["time_end"])):
            raise ValueError(f"time span differs from annotation: {source_id}")
        path = videos / source["filename"]
        if (not path.is_file() or path.stat().st_size != source["bytes"]
                or sha256(path) != source["video_sha256"]):
            raise ValueError(f"video bytes differ from committed lock: {source_id}")
        records.append({"path": f"videos/{source['filename']}",
                        "label": class_maps[0][canonical], "class": label_name,
                        "source_id": source_id, "bytes": source["bytes"],
                        "video_sha256": source["video_sha256"]})
    result = {"meta": {"source": sources["source"],
                       "locked_commit": lock_commit,
                       "selected_ids_sha256": sources["selected_ids_sha256"],
                       "selected_sources_sha256": sha256(sources_path),
                       "selected_source_fingerprint":
                       sources["selected_source_fingerprint"],
                       "annotation_sha256": sources["annotation_sha256"],
                       "clips": len(records), "analyzers":
                       ["r2plus1d_18", "r3d_18", "mc3_18"]},
              "test": records}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    print(json.dumps({"index_sha256": sha256(out_path),
                      "source_fingerprint": sources["selected_source_fingerprint"],
                      "clips": len(records)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ids", "index"))
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--exclude-inventory", type=Path, action="append", default=[])
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--ids-out", type=Path, default=REPO / IDS_REL)
    parser.add_argument("--sources-out", type=Path, default=REPO / SOURCES_REL)
    parser.add_argument("--lock-commit")
    parser.add_argument("--index-out", type=Path,
                        default=REPO / "configs/holdout_source_audit/index.json")
    args = parser.parse_args()
    if args.mode == "ids":
        if args.selection is None or not args.exclude_inventory:
            parser.error("ids mode requires selection and exclusion inventories")
        lock_ids(args.selection, args.annotation, args.exclude_inventory,
                 args.videos, args.ids_out, args.sources_out)
    else:
        if not args.lock_commit:
            parser.error("index mode requires a committed ID lock")
        build_index(args.lock_commit, args.ids_out, args.sources_out,
                    args.annotation, args.videos, args.index_out)


if __name__ == "__main__":
    main()
