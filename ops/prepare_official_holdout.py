#!/usr/bin/env python
"""ID-only audit and decode preflight for official Kinetics-400 validation.

This command never loads labels into the selection logic and never runs an
action-recognition model. It can stream official tar archives while retaining
only hash-ranked candidate clips. Its output is a *candidate* holdout; the
exact selected IDs and index must still be committed before evaluation.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import re
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

SALT = "v2c-holdout-20260927"
SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
MEMBER_RE = re.compile(r"^([A-Za-z0-9_-]{11})_(\d{6})_(\d{6})\.mp4$")
OFFICIAL_PREFIX = "https://s3.amazonaws.com/kinetics/400/val/"
REPO = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def id_fingerprint(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def load_exclusion(path: Path) -> set[str]:
    inventory = json.loads(path.read_text(encoding="utf-8"))
    ids = inventory["source_ids"]
    if (not isinstance(ids, list) or ids != sorted(set(ids))
            or any(not SOURCE_RE.fullmatch(key) for key in ids)
            or inventory["source_count"] != len(ids)
            or inventory["source_fingerprint"] != id_fingerprint(ids)):
        raise ValueError(f"invalid legacy source inventory: {path}")
    return set(ids)


def ranked_ids(annotation: Path, exclusions: set[str]) -> tuple[list[str], dict]:
    with annotation.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"youtube_id", "time_start", "time_end"} <= set(reader.fieldnames or []):
            raise ValueError("official K400 validation annotation schema changed")
        ids = [row["youtube_id"] for row in reader]
    if any(not SOURCE_RE.fullmatch(key) for key in ids) or len(ids) != len(set(ids)):
        raise ValueError("invalid or duplicate official validation source IDs")
    eligible = set(ids) - exclusions
    ranked = sorted(eligible, key=lambda key: (
        hashlib.sha256(f"{SALT}\0{key}".encode()).hexdigest(), key))
    return ranked, {"annotation_rows": len(ids),
                    "excluded_source_overlap": len(set(ids) & exclusions),
                    "eligible_sources": len(eligible),
                    "eligible_fingerprint": id_fingerprint(sorted(eligible))}


def archive_urls(path: Path) -> list[str]:
    urls = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if (len(urls) != 20 or len(set(urls)) != 20
            or any(not url.startswith(OFFICIAL_PREFIX)
                   or not url.endswith(".tar.gz") for url in urls)):
        raise ValueError("official K400 validation archive list changed")
    return urls


class HashingReader:
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        data = self.source.read(size)
        self.digest.update(data)
        return data


def stream_archive(url: str, candidate_ids: set[str], out_dir: Path) -> dict:
    videos = out_dir / "videos"
    videos.mkdir(parents=True, exist_ok=True)
    retained = []
    members_seen = 0
    with urllib.request.urlopen(url, timeout=120) as response:
        if response.status != 200:
            raise RuntimeError(f"archive HTTP status {response.status}: {url}")
        compressed_length = int(response.headers.get("Content-Length", "0"))
        reader = HashingReader(response)
        with tarfile.open(fileobj=reader, mode="r|gz") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                members_seen += 1
                filename = Path(member.name).name
                match = MEMBER_RE.fullmatch(filename)
                if match is None or match.group(1) not in candidate_ids:
                    continue
                source_id = match.group(1)
                destination = videos / filename
                temporary = destination.with_suffix(".mp4.partial")
                digest = hashlib.sha256()
                total = 0
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError(f"cannot read tar member {member.name}")
                with source, temporary.open("wb") as output:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        output.write(block)
                        digest.update(block)
                        total += len(block)
                if total != member.size:
                    raise RuntimeError(f"truncated tar member {member.name}")
                if destination.exists() and sha256(destination) != digest.hexdigest():
                    raise RuntimeError(f"duplicate source with differing bytes: {filename}")
                temporary.replace(destination)
                retained.append({"source_id": source_id, "filename": filename,
                                 "bytes": total, "sha256": digest.hexdigest()})
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            pass
    return {"url": url, "compressed_bytes": compressed_length,
            "compressed_sha256": reader.digest.hexdigest(),
            "members_seen": members_seen, "retained": retained}


def preflight(ranked: list[str], candidate_limit: int, target: int,
              out_dir: Path) -> dict:
    import cv2

    available: dict[str, list[Path]] = {}
    for path in (out_dir / "videos").glob("*.mp4"):
        match = MEMBER_RE.fullmatch(path.name)
        if match and match.group(1) in set(ranked[:candidate_limit]):
            available.setdefault(match.group(1), []).append(path)
    selected, failures = [], []
    for source_id in ranked[:candidate_limit]:
        files = available.get(source_id, [])
        if len(files) != 1:
            failures.append({"source_id": source_id,
                             "reason": "missing" if not files else "multiple_clips"})
            continue
        path = files[0]
        capture = cv2.VideoCapture(str(path))
        ok, frame = capture.read()
        capture.release()
        if not ok or frame is None or frame.size == 0:
            failures.append({"source_id": source_id, "reason": "undecodable"})
            continue
        selected.append({"source_id": source_id, "filename": path.name,
                         "video_sha256": sha256(path),
                         "bytes": path.stat().st_size})
        if len(selected) == target:
            break
    return {"target": target, "candidate_limit": candidate_limit,
            "selected": selected, "failures_before_target": failures,
            "selected_source_fingerprint": id_fingerprint(
                [row["source_id"] for row in selected]),
            "complete": len(selected) == target}


def archive_part(number: int, url: str, candidate_ids: set[str],
                 out_dir: Path) -> tuple[int, dict]:
    """Resume a verified part or stream one official archive independently."""
    path = out_dir / "parts" / f"part_{number:02d}.json"
    if path.exists():
        result = json.loads(path.read_text(encoding="utf-8"))
        if result.get("url") != url:
            raise ValueError("stale archive-part manifest")
        for row in result.get("retained", []):
            video = out_dir / "videos" / row["filename"]
            if (not video.is_file() or video.stat().st_size != row["bytes"]
                    or sha256(video) != row["sha256"]):
                raise ValueError(f"archive-part video missing or changed: {video}")
    else:
        # An interrupted archive has no committed part manifest. Re-read it
        # from byte zero so the compressed SHA-256 still covers the full source.
        for attempt in range(5):
            try:
                result = stream_archive(url, candidate_ids, out_dir)
                break
            except (TimeoutError, ConnectionError, urllib.error.URLError):
                if attempt == 4:
                    raise
                time.sleep(min(2 ** attempt, 8))
        temporary = path.with_suffix(".json.partial")
        temporary.write_text(json.dumps(result, indent=2) + "\n",
                             encoding="utf-8")
        temporary.replace(path)
    return number, result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--archive-paths", type=Path, required=True)
    parser.add_argument("--exclude-inventory", type=Path, action="append", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--candidate-limit", type=int, default=2000)
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=1,
                        help="parallel official archives; each part is independently hashed")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.target != 1000 or args.candidate_limit < args.target:
        raise ValueError("frozen target is 1,000; candidate limit must cover it")
    if not 1 <= args.workers <= 8:
        raise ValueError("workers must be between 1 and 8")
    excluded: set[str] = set()
    for path in args.exclude_inventory:
        excluded |= load_exclusion(path)
    ranked, audit = ranked_ids(args.annotation, excluded)
    urls = archive_urls(args.archive_paths)
    if len(ranked) < args.candidate_limit:
        raise ValueError("not enough metadata candidates")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    code_commit = subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", "rev-parse", "HEAD"],
        cwd=REPO, text=True).strip()
    plan = {"status": "metadata_only" if not args.download else "preflight",
            "source": "official CVDF Kinetics-400 validation",
            "salt": SALT, "annotation_sha256": sha256(args.annotation),
            "archive_path_list_sha256": sha256(args.archive_paths),
            "legacy_inventories": [{"path": path.name, "sha256": sha256(path)}
                                   for path in args.exclude_inventory],
            "source_audit": audit, "candidate_limit": args.candidate_limit,
            "target": args.target, "code_commit": code_commit,
            "candidate_ids_sha256": id_fingerprint(ranked[:args.candidate_limit])}
    (args.out_dir / "candidate_plan.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "candidate_ids.txt").write_text(
        "\n".join(ranked[:args.candidate_limit]) + "\n", encoding="utf-8")
    print(json.dumps({"audit": audit, "candidate_limit": args.candidate_limit}))
    if not args.download:
        return
    parts_dir = args.out_dir / "parts"
    parts_dir.mkdir(exist_ok=True)
    candidate_ids = set(ranked[:args.candidate_limit])
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(archive_part, number, url, candidate_ids,
                                   args.out_dir)
                   for number, url in enumerate(urls)]
        for future in as_completed(futures):
            number, result = future.result()
            print(f"[holdout-preflight] archive {number + 1}/{len(urls)} "
                  f"retained={len(result['retained'])}", flush=True)
    selection = preflight(ranked, args.candidate_limit, args.target, args.out_dir)
    (args.out_dir / "preflight_selection.json").write_text(
        json.dumps({**plan, **selection}, indent=2) + "\n", encoding="utf-8")
    if not selection["complete"]:
        raise RuntimeError("CHƯA ĐO: fewer than 1,000 readable source videos")
    print(f"[holdout-preflight] 1,000 readable sources; fingerprint "
          f"{selection['selected_source_fingerprint']}")


if __name__ == "__main__":
    main()
