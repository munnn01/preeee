#!/usr/bin/env python
"""Two-phase V4 holdout lock: commit video IDs/hashes before reading labels."""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from pathlib import Path

from ops.prepare_official_holdout import (REPO, MEMBER_RE, SOURCE_RE,
                                          id_fingerprint, sha256)
from ops.prepare_v4_holdout import AUDIT_REL, SALT, plan

IDS_REL = f"{AUDIT_REL}/selected_ids.txt"
SOURCES_REL = f"{AUDIT_REL}/selected_sources.json"
INDEX_REL = f"{AUDIT_REL}/index.json"


def git(*args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", *args], cwd=REPO)


def verify_ranked_selection(ranked: list[str], selected: list[dict],
                            failures: list[dict]) -> None:
    if len(selected) != 1000 or not isinstance(failures, list):
        raise ValueError("V4 requires 1,000 selected videos")
    ids = [row["source_id"] for row in selected]
    failed = [row["source_id"] for row in failures]
    if (len(set(ids)) != 1000 or len(set(failed)) != len(failed)
            or set(ids) & set(failed)
            or any(not SOURCE_RE.fullmatch(key) for key in ids + failed)
            or any(row.get("reason") not in
                   {"missing", "multiple_clips", "undecodable"} for row in failures)
            or ids[-1] not in ranked):
        raise ValueError("invalid V4 selection IDs or failure list")
    prefix = ranked[:ranked.index(ids[-1]) + 1]
    if ([key for key in prefix if key not in set(failed)] != ids
            or set(prefix) != set(ids) | set(failed)):
        raise ValueError("V4 selection deviates from hash rank")


def matches_locked_metadata(selection: dict, locked_plan: dict) -> bool:
    """Preflight advances status while every locked source field stays fixed."""
    return (selection.get("status") == "preflight"
            and {key: selection.get(key) for key in locked_plan if key != "status"}
            == {key: value for key, value in locked_plan.items()
                if key != "status"})


def lock_ids(selection_path: Path, annotation: Path, archive_paths: Path,
             legacy: list[Path], dev_manifest: Path, videos: Path,
             ids_out: Path, sources_out: Path) -> dict:
    locked_plan_path = REPO / AUDIT_REL / "candidate_plan.json"
    locked_ids_path = REPO / AUDIT_REL / "candidate_ids.txt"
    for rel, path in (("candidate_plan.json", locked_plan_path),
                      ("candidate_ids.txt", locked_ids_path)):
        if git("show", f"HEAD:{AUDIT_REL}/{rel}") != path.read_bytes():
            raise ValueError("V4 candidate metadata is not committed")
    locked_plan = json.loads(locked_plan_path.read_text(encoding="utf-8"))
    current, ranked = plan(annotation, archive_paths, legacy, dev_manifest)
    if ({k: v for k, v in current.items() if k != "code_commit"}
            != {k: v for k, v in locked_plan.items() if k != "code_commit"}
            or ranked != locked_ids_path.read_text(encoding="utf-8").splitlines()):
        raise ValueError("V4 source plan changed after metadata lock")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if (not matches_locked_metadata(selection, locked_plan)
            or selection.get("salt") != SALT
            or selection.get("complete") is not True
            or selection.get("target") != 1000
            or selection.get("candidate_limit") != 2000):
        raise ValueError("V4 preflight does not match locked metadata")
    selected = selection["selected"]
    failures = selection["failures_before_target"]
    verify_ranked_selection(ranked, selected, failures)
    ids = [row["source_id"] for row in selected]
    if selection["selected_source_fingerprint"] != id_fingerprint(ids):
        raise ValueError("V4 selected-source fingerprint changed")
    found = {}
    archive_parts = []
    urls = archive_paths.read_text(encoding="utf-8").splitlines()
    for number in range(20):
        path = selection_path.parent / "parts" / f"part_{number:02d}.json"
        part = json.loads(path.read_text(encoding="utf-8"))
        previous = json.loads((REPO / "configs/holdout_source_audit/archive_parts" /
                               path.name).read_text(encoding="utf-8"))
        if (part["url"] != urls[number]
                or part["url"] != previous["url"]
                or part["compressed_sha256"] != previous["compressed_sha256"]
                or part["members_seen"] != previous["members_seen"]):
            raise ValueError("V4 archive bytes/order differ from official V2 audit")
        archive_parts.append({"path": path.name, "sha256": sha256(path),
                              "compressed_sha256": part["compressed_sha256"]})
        for row in part["retained"]:
            found.setdefault(row["source_id"], []).append(row)
    for row in selected:
        path = videos / row["filename"]
        match = MEMBER_RE.fullmatch(row["filename"])
        records = found.get(row["source_id"], [])
        if (match is None or match.group(1) != row["source_id"]
                or len(records) != 1
                or records[0]["filename"] != row["filename"]
                or records[0]["sha256"] != row["video_sha256"]
                or records[0]["bytes"] != row["bytes"]
                or not path.is_file() or path.stat().st_size != row["bytes"]
                or sha256(path) != row["video_sha256"]):
            raise ValueError(f"missing, changed or duplicate V4 video: {row['source_id']}")
    ids_out.parent.mkdir(parents=True, exist_ok=True)
    ids_out.write_text("\n".join(ids) + "\n", encoding="utf-8", newline="\n")
    sources = {"source": locked_plan["source"], "salt": SALT,
               "selected": selected, "failures_before_target": failures,
               "target": 1000, "candidate_limit": 2000,
               "candidate_plan_sha256": sha256(locked_plan_path),
               "candidate_ids_sha256": sha256(locked_ids_path),
               "preflight_selection_sha256": sha256(selection_path),
               "selected_ids_sha256": sha256(ids_out),
               "selected_source_fingerprint": id_fingerprint(ids),
               "annotation_sha256": locked_plan["annotation_sha256"],
               "archive_path_list_sha256": locked_plan["archive_path_list_sha256"],
               "archive_parts": archive_parts,
               "preflight_code_commit": locked_plan["code_commit"]}
    sources_out.write_text(json.dumps(sources, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
    return {"count": len(ids), "fingerprint": sources["selected_source_fingerprint"],
            "ids_sha256": sha256(ids_out), "sources_sha256": sha256(sources_out)}


def committed_lock(lock_commit: str, ids_path: Path,
                   sources_path: Path) -> tuple[list[str], dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", lock_commit):
        raise ValueError("full V4 ID lock commit required")
    subprocess.run(["git", "-c", f"safe.directory={REPO.as_posix()}",
                    "merge-base", "--is-ancestor", lock_commit, "HEAD"],
                   cwd=REPO, check=True)
    for rel, path in ((IDS_REL, ids_path), (SOURCES_REL, sources_path)):
        if git("show", f"{lock_commit}:{rel}") != path.read_bytes():
            raise ValueError(f"V4 ID lock differs from commit: {rel}")
    ids = ids_path.read_text(encoding="utf-8").splitlines()
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    if (len(ids) != 1000 or len(set(ids)) != 1000
            or [row["source_id"] for row in sources["selected"]] != ids
            or sources["selected_source_fingerprint"] != id_fingerprint(ids)
            or sources["selected_ids_sha256"] != sha256(ids_path)):
        raise ValueError("invalid committed V4 source list")
    return ids, sources


def build_index(lock_commit: str, ids_path: Path, sources_path: Path,
                annotation: Path, videos: Path, out_path: Path) -> dict:
    ids, sources = committed_lock(lock_commit, ids_path, sources_path)
    if sha256(annotation) != sources["annotation_sha256"]:
        raise ValueError("annotation bytes differ from V4 ID lock")
    # No label column is accessed before the committed ID lock succeeds.
    with annotation.open(encoding="utf-8", newline="") as stream:
        annotations = {row["youtube_id"]: row for row in csv.DictReader(stream)}
    from src.tasks.action_recognition import kinetics_category_index
    class_maps = [kinetics_category_index(name) for name in
                  ("r2plus1d_18", "r3d_18", "mc3_18")]
    if class_maps[0] != class_maps[1] or class_maps[0] != class_maps[2]:
        raise ValueError("V4 analyzer label orders differ")
    records = []
    for source in sources["selected"]:
        key = source["source_id"]
        annotation_row = annotations[key]
        label_name = annotation_row["label"]
        canonical = re.sub(r"[^a-z0-9]+", " ", label_name.lower()).strip()
        if canonical not in class_maps[0]:
            raise ValueError(f"unmapped Kinetics label: {label_name}")
        match = MEMBER_RE.fullmatch(source["filename"])
        if (match is None or match.group(1) != key
                or int(match.group(2)) != int(annotation_row["time_start"])
                or int(match.group(3)) != int(annotation_row["time_end"])):
            raise ValueError(f"V4 source span differs from annotation: {key}")
        video = videos / source["filename"]
        if (not video.is_file() or video.stat().st_size != source["bytes"]
                or sha256(video) != source["video_sha256"]):
            raise ValueError(f"V4 video bytes differ from source lock: {key}")
        records.append({"path": f"videos/{source['filename']}",
                        "label": class_maps[0][canonical], "class": label_name,
                        "source_id": key, "bytes": source["bytes"],
                        "video_sha256": source["video_sha256"]})
    result = {"meta": {"source": sources["source"], "locked_commit": lock_commit,
                       "selected_ids_sha256": sources["selected_ids_sha256"],
                       "selected_sources_sha256": sha256(sources_path),
                       "selected_source_fingerprint":
                       sources["selected_source_fingerprint"],
                       "annotation_sha256": sources["annotation_sha256"],
                       "clips": len(records),
                       "analyzers": ["r2plus1d_18", "r3d_18", "mc3_18"]},
              "test": records}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
    return {"index_sha256": sha256(out_path),
            "fingerprint": sources["selected_source_fingerprint"],
            "clips": len(records)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ids", "index"))
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--archive-paths", type=Path)
    parser.add_argument("--exclude-inventory", type=Path, action="append", default=[])
    parser.add_argument("--dev-manifest", type=Path)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--ids-out", type=Path, default=REPO / IDS_REL)
    parser.add_argument("--sources-out", type=Path, default=REPO / SOURCES_REL)
    parser.add_argument("--index-out", type=Path, default=REPO / INDEX_REL)
    parser.add_argument("--lock-commit")
    args = parser.parse_args()
    if args.mode == "ids":
        if (args.selection is None or args.archive_paths is None
                or args.dev_manifest is None or not args.exclude_inventory):
            parser.error("ids mode requires preflight and ID-only inputs")
        print(json.dumps(lock_ids(args.selection, args.annotation, args.archive_paths,
                                  args.exclude_inventory, args.dev_manifest,
                                  args.videos, args.ids_out, args.sources_out)))
    else:
        if not args.lock_commit:
            parser.error("index mode requires a committed ID lock")
        print(json.dumps(build_index(args.lock_commit, args.ids_out,
                                     args.sources_out, args.annotation,
                                     args.videos, args.index_out)))


if __name__ == "__main__":
    main()
