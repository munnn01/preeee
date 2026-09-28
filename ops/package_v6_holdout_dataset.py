#!/usr/bin/env python
"""Package only committed V6 holdout video bytes for private Kaggle transfer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import zipfile

from ops.lock_v6_holdout import REPO, SOURCES_REL, sha256
from ops.paper_holdout_v6 import MANIFEST, ready_index


def zip_selected(sources: list[dict], videos: Path, out: Path) -> tuple[int, int]:
    names = [f"videos/{row['filename']}" for row in sources]
    if len(names) != len(set(names)):
        raise ValueError("duplicate selected V6 video filename")
    total = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED,
                         allowZip64=True) as archive:
        for row, name in zip(sources, names):
            path = videos / row["filename"]
            if (not path.is_file() or path.stat().st_size != row["bytes"]
                    or sha256(path) != row["video_sha256"]):
                raise ValueError(f"V6 video bytes changed during package: {name}")
            archive.write(path, arcname=name)
            total += row["bytes"]
    with zipfile.ZipFile(out) as archive:
        if archive.namelist() != names:
            raise ValueError("V6 ZIP member order differs from selected source lock")
    return len(names), total


def package(prereg_commit: str, video_root: Path, out_dir: Path,
            account: str, slug: str) -> dict:
    if (not re.fullmatch(r"[a-z0-9]+", account)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug)):
        raise ValueError("invalid private Kaggle dataset identity")
    if out_dir.exists():
        raise ValueError("V6 package destination must be new")
    ready_index(REPO / "configs/v6_holdout_source_audit/index.json",
                prereg_commit, video_root)
    sources_path = REPO / SOURCES_REL
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True)
    zip_path = out_dir / "videos.zip"
    count, total = zip_selected(sources["selected"], video_root / "videos",
                                zip_path)
    if count != 1000:
        raise ValueError("V6 package requires exactly 1,000 videos")
    index_path = REPO / "configs/v6_holdout_source_audit/index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    manifest = {"scope": "private V6 holdout transfer; no labels in this package",
                "analysis_lock_commit": prereg_commit,
                "id_lock_commit": index["meta"]["locked_commit"],
                "index_sha256": sha256(index_path),
                "selected_sources_sha256": sha256(sources_path),
                "freeze_manifest_sha256": sha256(MANIFEST),
                "source_fingerprint": sources["selected_source_fingerprint"],
                "source_count": count, "source_video_bytes": total,
                "zip_bytes": zip_path.stat().st_size,
                "zip_sha256": sha256(zip_path),
                "seed": 20261001, "bootstrap_unit": "source video",
                "bootstrap_draws_after_merge": 2000}
    (out_dir / "v6_holdout_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    metadata = {"title": "V6 locked K400 validation holdout",
                "id": f"{account}/{slug}", "licenses": [{"name": "other"}],
                "description": "Private research transfer of 1000 official Kinetics-400 validation videos for a frozen V6 policy. Original rights remain with the respective authors. Source hashes and preregistration commit are in v6_holdout_manifest.json. Do not publish this dataset."}
    (out_dir / "dataset-metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg-commit", required=True)
    parser.add_argument("--video-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()
    manifest = package(args.prereg_commit, args.video_root, args.out_dir,
                       args.account, args.slug)
    print(json.dumps({"source_count": manifest["source_count"],
                      "source_fingerprint": manifest["source_fingerprint"],
                      "zip_sha256": manifest["zip_sha256"]}))


if __name__ == "__main__":
    main()
