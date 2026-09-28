#!/usr/bin/env python
"""Package only original V2 pilot FIT/CALIBRATION/DEV caches for private V5 Kaggle use."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import tarfile

from ops.v3_dev_policy import EXPECTED_FINGERPRINTS, file_sha256
from ops.v4_dev_policy import COUNTS, PILOT_INDEX_SHA256, load_development
from ops.v5_dev_agreement import PREREG_COMMIT


def package(roots: dict[str, Path], out_dir: Path, account: str, slug: str) -> dict:
    if (not re.fullmatch(r"[a-z0-9]+", account)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug)):
        raise ValueError("invalid private Kaggle dataset identity")
    if set(roots) != {"h264", "h265"} or out_dir.exists():
        raise ValueError("two codec roots and a new package directory are required")
    loaded = {codec: load_development(roots[codec], codec)
              for codec in ("h264", "h265")}
    files_to_package = []
    for codec in ("h264", "h265"):
        root = roots[codec].resolve()
        files_to_package.extend((root / name, codec, root) for name in
                                ("manifest.json", "risk_model.json", "frozen_policy.json"))
        for stage, count in COUNTS.items():
            files = sorted((root / "cache" / stage).glob("clip_*.json"))
            if len(files) != count:
                raise ValueError(f"{codec} {stage} cache count changed")
            files_to_package.extend((path, codec, root) for path in files)
    out_dir.mkdir(parents=True)
    archive = out_dir / "v5_dev_cache.tar.gz"
    with tarfile.open(archive, "w:gz") as target:
        for path, codec, root in files_to_package:
            arcname = Path("dual_codec_search_v2") / codec / path.relative_to(root)
            target.add(path, arcname=arcname.as_posix(), recursive=False)
    provenance = {codec: loaded[codec][5] for codec in ("h264", "h265")}
    manifest = {
        "scope": "private original V2 pilot FIT/CALIBRATION/DEV cache; no TEST/holdout or transfer analyzer",
        "preregistration_commit": PREREG_COMMIT,
        "source_fingerprints": EXPECTED_FINGERPRINTS,
        "stage_counts_per_codec": COUNTS,
        "pilot_index_sha256": PILOT_INDEX_SHA256,
        "input_provenance": provenance,
        "archive_file": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": file_sha256(archive),
        "dataset_id": f"{account}/{slug}",
    }
    (out_dir / "v5_dev_cache_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "dataset-metadata.json").write_text(
        json.dumps({"title": "V5 private original DEV cache",
                    "id": f"{account}/{slug}",
                    "licenses": [{"name": "other"}],
                    "description": "Private research cache from the preregistered V2 pilot: FIT, CALIBRATION, DEV only. No holdout or transfer analyzer. Source and archive hashes are in v5_dev_cache_manifest.json."},
                   indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h264-cache-root", type=Path, required=True)
    parser.add_argument("--h265-cache-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()
    result = package({"h264": args.h264_cache_root,
                      "h265": args.h265_cache_root}, args.out_dir,
                     args.account, args.slug)
    print(json.dumps({"dataset_id": result["dataset_id"],
                      "archive_sha256": result["archive_sha256"],
                      "archive_bytes": result["archive_bytes"]}))


if __name__ == "__main__":
    main()
