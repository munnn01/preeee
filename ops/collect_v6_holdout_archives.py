#!/usr/bin/env python
"""Verify four Kaggle byte-only shards and derive the V6 preflight selection.

This transport step never reads the annotation or any analyzer output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from ops.prepare_official_holdout import MEMBER_RE, preflight, sha256
from ops.v6_holdout_archive_shard import IDS, PLAN, PRIOR_PARTS, locked_inputs


def safe_members(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    members = {}
    for member in archive.getmembers():
        name = member.name.removeprefix("./")
        if member.isdir() and name.rstrip("/") in {"parts", "videos"}:
            continue
        if (not member.isfile() or name in members
                or (name != member.name and member.name != "./" + name)
                or (name != "shard_manifest.json"
                    and not (name.startswith("parts/part_") and name.endswith(".json"))
                    and not (name.startswith("videos/")
                             and MEMBER_RE.fullmatch(name.removeprefix("videos/"))))):
            raise ValueError(f"unsafe or duplicate Kaggle tar member: {member.name}")
        members[name] = member
    return members


def read_json_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> dict:
    stream = archive.extractfile(member)
    if stream is None or member.size > 10_000_000:
        raise ValueError("invalid JSON member")
    return json.loads(stream.read().decode("utf-8"))


def copy_verified_member(archive: tarfile.TarFile, member: tarfile.TarInfo,
                         destination: Path, expected_sha: str,
                         expected_bytes: int) -> None:
    if destination.exists() or member.size != expected_bytes:
        raise ValueError(f"duplicate or wrong-sized member: {member.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = archive.extractfile(member)
    if source is None:
        raise ValueError(f"unreadable member: {member.name}")
    digest = hashlib.sha256()
    with source, destination.open("xb") as output:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            output.write(block)
            digest.update(block)
    if digest.hexdigest() != expected_sha or destination.stat().st_size != expected_bytes:
        destination.unlink()
        raise ValueError(f"member SHA-256 differs: {member.name}")


def collect(tars: list[Path], out_dir: Path, expected_commit: str) -> dict:
    if len(tars) != 4 or out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError("exactly four shards and a new output directory required")
    plan, candidates, urls = locked_inputs()
    (out_dir / "parts").mkdir(parents=True, exist_ok=True)
    ranges, seen_parts, seen_videos = [], set(), set()
    for path in tars:
        with tarfile.open(path, "r:") as archive:
            members = safe_members(archive)
            if "shard_manifest.json" not in members:
                raise ValueError("Kaggle shard manifest missing")
            shard = read_json_member(archive, members["shard_manifest.json"])
            start, stop = shard["part_start"], shard["part_stop"]
            if (shard["experiment"] != "v6_h265_byte_only_preflight"
                    or shard["code_commit"] != expected_commit
                    or shard["candidate_plan_sha256"] != sha256(PLAN)
                    or shard["candidate_ids_sha256"] != sha256(IDS)
                    or shard["candidate_ids_fingerprint"] !=
                    plan["candidate_ids_fingerprint"]
                    or not (0 <= start < stop <= 20)
                    or [row["number"] for row in shard["parts"]] !=
                    list(range(start, stop))):
                raise ValueError("Kaggle shard provenance differs from source lock")
            ranges.append((start, stop))
            expected_members = {"shard_manifest.json"}
            for entry in shard["parts"]:
                number = entry["number"]
                name = f"parts/part_{number:02d}.json"
                if number in seen_parts or name not in members:
                    raise ValueError("missing or duplicate archive part")
                seen_parts.add(number)
                part = read_json_member(archive, members[name])
                previous = json.loads((PRIOR_PARTS / f"part_{number:02d}.json").read_text())
                if (part["url"] != urls[number] or part["url"] != previous["url"]
                        or part["compressed_sha256"] != previous["compressed_sha256"]
                        or part["members_seen"] != previous["members_seen"]
                        or entry["compressed_sha256"] != part["compressed_sha256"]
                        or entry["retained_count"] != len(part["retained"])):
                    raise ValueError("official archive bytes/order changed")
                raw = archive.extractfile(members[name]).read()
                if hashlib.sha256(raw).hexdigest() != entry["manifest_sha256"]:
                    raise ValueError("archive-part manifest SHA-256 changed")
                (out_dir / name).write_bytes(raw)
                expected_members.add(name)
                for row in part["retained"]:
                    video_name = "videos/" + row["filename"]
                    if (row["source_id"] not in candidates
                            or video_name in seen_videos or video_name not in members):
                        raise ValueError("unexpected or duplicate candidate video")
                    seen_videos.add(video_name)
                    expected_members.add(video_name)
                    copy_verified_member(archive, members[video_name],
                                         out_dir / video_name,
                                         row["sha256"], row["bytes"])
            if set(members) != expected_members:
                raise ValueError("Kaggle tar contains unrecorded members")
    if seen_parts != set(range(20)) or sorted(ranges) != [(0, 5), (5, 10),
                                                         (10, 15), (15, 20)]:
        raise ValueError("V6 preflight requires exactly 20 disjoint archive parts")
    selection = preflight(candidates, 2000, 1000, out_dir)
    (out_dir / "preflight_selection.json").write_text(
        json.dumps({**plan, **selection, "status": "preflight"}, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    report = {"complete": selection["complete"],
              "selected": len(selection["selected"]),
              "selected_source_fingerprint": selection["selected_source_fingerprint"],
              "preflight_selection_sha256": sha256(out_dir / "preflight_selection.json"),
              "tar_sha256": {path.name: sha256(path) for path in tars},
              "video_count": len(seen_videos)}
    (out_dir / "transport_audit.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not selection["complete"]:
        raise RuntimeError("CHƯA ĐO: fewer than 1,000 valid sources")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tar", type=Path, action="append", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    print(json.dumps(collect(args.tar, args.out_dir, args.expected_commit)))


if __name__ == "__main__":
    main()
