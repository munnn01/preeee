#!/usr/bin/env python
"""Verify and preserve both full five-QP DEV runtime results byte-for-byte."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from ops.codec_search_ar import QPS
from src.models.codec_search import CANDIDATES

REPO = Path(__file__).resolve().parents[1]
SAMPLE_IDS = REPO / "configs/paper_runtime_dev/sample_ids.json"
SOURCE_FILES = REPO / "configs/paper_runtime_dev/source_files.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_result(path: Path, codec: str, index_sha: str,
                    input_check: dict, expected_commit: str) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    manifest, summary, records = (report[key] for key in
                                  ("manifest", "summary", "records"))
    ids = json.loads(SAMPLE_IDS.read_text(encoding="utf-8"))
    if (manifest.get("experiment") != "dual_v2_full_runtime"
            or manifest.get("codec") != codec or manifest.get("split") != "val"
            or manifest.get("clips") != 20 or manifest.get("sample_ids") != ids
            or manifest.get("sample_ids_sha256") != sha256(SAMPLE_IDS)
            or manifest.get("sample_fingerprint") != input_check["sample_fingerprint"]
            or manifest.get("index_sha256") != index_sha
            or manifest.get("code_commit") != expected_commit
            or manifest.get("qps") != list(QPS)
            or manifest.get("candidates") != list(CANDIDATES)):
        raise ValueError(f"runtime manifest does not match frozen DEV design: {codec}")
    if (len(records) != 20 or [row["sequence_id"] for row in records] != ids
            or summary.get("n") != 20
            or summary.get("identity_codec_calls_per_clip") != 5
            or summary.get("full_codec_calls_per_clip") != 30):
        raise ValueError(f"runtime records or summary incomplete: {codec}")
    for row in records:
        if (row.get("identity_codec_calls") != 5
                or row.get("full_codec_calls") != 30
                or [qp["qp"] for qp in row.get("qps", [])] != list(QPS)
                or set(row.get("arm_order", [])) != {"identity", "full"}
                or row.get("identity_only_s", 0) <= 0
                or row.get("full_selector_s", 0) <= 0
                or row.get("identity_peak_process_tree_rss_bytes", 0) <= 0
                or row.get("full_peak_process_tree_rss_bytes", 0) <= 0):
            raise ValueError(f"runtime clip lacks full timing/memory: {codec}")
    sidecar = path.with_name("runtime_result.sha256")
    if sidecar.read_text(encoding="utf-8").split()[0] != sha256(path):
        raise ValueError(f"runtime result SHA sidecar differs: {codec}")
    return report


def package(source_dir: Path, index_path: Path, input_check_path: Path,
            out_dir: Path, expected_commit: str) -> None:
    input_check = json.loads(input_check_path.read_text(encoding="utf-8"))
    index_sha = sha256(index_path)
    ids = json.loads(SAMPLE_IDS.read_text(encoding="utf-8"))
    if (input_check.get("source_check") != "20/20 SHA-256 matched"
            or input_check.get("sample_ids") != ids
            or input_check.get("source_files_sha256") != sha256(SOURCE_FILES)
            or input_check.get("index_sha256") != index_sha):
        raise ValueError("runtime source-video verification is incomplete")
    reports = {codec: validate_result(
        source_dir / codec / "runtime_result.json", codec, index_sha,
        input_check, expected_commit) for codec in ("h264", "h265")}
    if (reports["h264"]["manifest"]["hardware"] !=
            reports["h265"]["manifest"]["hardware"]
            or reports["h264"]["manifest"]["versions"] !=
            reports["h265"]["manifest"]["versions"]):
        raise ValueError("codec arms were not measured on the same hardware/software")
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for codec in ("h264", "h265"):
        source = source_dir / codec / "runtime_result.json"
        target = out_dir / f"{codec}_result.json"
        shutil.copyfile(source, target)
        files.append(target)
    for source, name in ((index_path, "kaggle_index.json"),
                         (input_check_path, "runtime_input_check.json")):
        target = out_dir / name
        shutil.copyfile(source, target)
        files.append(target)
    provenance = {"experiment": "v2c_full_runtime_package",
                  "scope": "20 fixed old-DEV videos, both codecs, one GPU machine",
                  "execution_code_commit": expected_commit,
                  "packaging_code_commit": subprocess.check_output(
                      ["git", "-c", f"safe.directory={REPO.as_posix()}",
                       "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                  "sample_selection_salt": "paper-runtime-v1-20260924",
                  "arm_order_salt": "paper-runtime-order-20260924",
                  "source_files_sha256": sha256(SOURCE_FILES),
                  "sample_ids_sha256": sha256(SAMPLE_IDS),
                  "index_sha256": index_sha,
                  "input_check_sha256": sha256(input_check_path),
                  "bootstrap_unit": "not applicable: descriptive paired runtime",
                  "bootstrap_draws": 0,
                  "result_sha256": {codec: sha256(out_dir / f"{codec}_result.json")
                                    for codec in ("h264", "h265")}}
    provenance_path = out_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
    files.append(provenance_path)
    (out_dir / "SHA256SUMS.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in files),
        encoding="utf-8", newline="\n")
    print(json.dumps(provenance, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--input-check", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--execution-commit", required=True)
    args = parser.parse_args()
    package(args.source_dir, args.index, args.input_check,
            args.out_dir, args.execution_commit)


if __name__ == "__main__":
    main()
