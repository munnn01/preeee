#!/usr/bin/env python
"""Audit and preserve the four preregistered holdout shard artifacts.

Run ``ops.paper_holdout_confirm merge`` for both codecs first. This command
never recalculates a quality metric; it verifies provenance and copies the
raw records needed to reproduce the already merged JSON results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from ops.rcts_pilot import clip_id

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "configs/holdout_source_audit/index.json"
PREREG_COMMIT = "4730d07df1e9593b56f475ccc395315358f9a49c"
LOCK_COMMIT = "c12f422ed85f8a4a61319fe169724c115f663f74"
FINGERPRINT = "ea86e9ba66b2fe3143a891619ae34ae036c7f065ea083f4b076b53263e9c668d"
SEED = 20260924
DRAWS = 2000
ASSIGNMENTS = (("shungg05", "h264", 0, "shungg05"),
               ("dieulinhh", "h264", 1, "dieulinhh"),
               ("huolgggnuyen", "h265", 0, "huolgggnuyen"),
               ("huolgggnuyen", "h265", 1, "huolgggnuyen_h265_s1"))
STAGES = (("primary", "primary_six_candidate"),
          ("mc3", "independent_mc3_selected_stream"))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def validate_shard(directory: Path, stage: str, codec: str, shard: int,
                   expected_ids: list[str], expected_sources: list[str],
                   index_sha: str, primary_sha: str | None = None) -> dict:
    manifest_path = directory / "manifest.json"
    records_path = directory / "shard_records.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = [json.loads(line) for line in
               records_path.read_text(encoding="utf-8").splitlines()]
    if (manifest.get("experiment") != "v2c_source_disjoint_holdout"
            or manifest.get("stage") != stage or manifest.get("codec") != codec
            or manifest.get("shard") != shard or manifest.get("shards") != 2
            or manifest.get("n") != 500 or len(records) != 500
            or manifest.get("sample_ids") != expected_ids
            or manifest.get("source_ids") != expected_sources
            or [row.get("sequence_id") for row in records] != expected_ids
            or manifest.get("source_fingerprint") != FINGERPRINT
            or manifest.get("index_sha256") != index_sha
            or manifest.get("preregistration_commit") != PREREG_COMMIT
            or manifest.get("code_commit") != PREREG_COMMIT
            or manifest.get("bootstrap_seed") != SEED
            or manifest.get("bootstrap_draws") != DRAWS
            or manifest.get("bootstrap_unit") !=
            "source video; all QPs, arms and analyzers paired"):
        raise ValueError(f"invalid or incomplete {codec} shard {shard} {stage}")
    if stage == STAGES[1][1] and manifest.get("primary_records_sha256") != primary_sha:
        raise ValueError("mc3 shard does not cite its exact primary records")
    return {"manifest_sha256": sha256(manifest_path),
            "records_sha256": sha256(records_path)}


def package(raw_root: Path, notebook_root: Path, input_manifest_path: Path,
            out_dir: Path) -> None:
    index_sha = sha256(INDEX)
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    if (index["meta"]["locked_commit"] != LOCK_COMMIT
            or index["meta"]["selected_source_fingerprint"] != FINGERPRINT
            or len(index["test"]) != 1000):
        raise ValueError("committed holdout index changed")
    input_manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))
    if (input_manifest.get("index_sha256") != index_sha
            or input_manifest.get("source_fingerprint") != FINGERPRINT
            or input_manifest.get("source_count") != 1000
            or input_manifest.get("preregistration_commit") != PREREG_COMMIT
            or input_manifest.get("id_lock_commit") != LOCK_COMMIT):
        raise ValueError("private Kaggle input manifest changed")
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = {"experiment": "v2c_source_disjoint_holdout_package",
                  "preregistration_commit": PREREG_COMMIT,
                  "id_lock_commit": LOCK_COMMIT,
                  "packaging_code_commit": subprocess.check_output(
                      ["git", "-c", f"safe.directory={REPO.as_posix()}",
                       "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                  "source_fingerprint": FINGERPRINT,
                  "index_sha256": index_sha,
                  "input_manifest_sha256": sha256(input_manifest_path),
                  "input_zip_sha256": input_manifest["zip_sha256"],
                  "bootstrap_unit": "source video; all QPs, arms and analyzers paired",
                  "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
                  "shards": [], "results": {}}
    shutil.copyfile(input_manifest_path, out_dir / "input_manifest.json")
    for account, codec, shard, notebook_folder in ASSIGNMENTS:
        source = raw_root / f"{codec}_shard{shard}"
        expected = index["test"][shard::2]
        expected_ids = [clip_id(row) for row in expected]
        expected_sources = [row["source_id"] for row in expected]
        hashes = {}
        for folder, stage in STAGES:
            source_dir = source / folder
            hashes[folder] = validate_shard(
                source_dir, stage, codec, shard, expected_ids,
                expected_sources, index_sha,
                hashes["primary"]["records_sha256"] if folder == "mc3" else None)
            target_dir = out_dir / "raw" / codec / f"shard_{shard}" / folder
            target_dir.mkdir(parents=True, exist_ok=True)
            for filename in ("manifest.json", "shard_records.jsonl"):
                shutil.copyfile(source_dir / filename, target_dir / filename)
                key = "manifest_sha256" if filename == "manifest.json" else "records_sha256"
                if sha256(target_dir / filename) != hashes[folder][key]:
                    raise ValueError("raw shard changed while copying")
        notebook_source = notebook_root / notebook_folder
        notebook_target = out_dir / "notebooks" / notebook_folder
        notebook_target.mkdir(parents=True, exist_ok=True)
        for filename in ("notebook.ipynb", "kernel-metadata.json"):
            shutil.copyfile(notebook_source / filename, notebook_target / filename)
        notebook_meta = json.loads((notebook_target / "kernel-metadata.json").read_text())
        if (notebook_meta.get("is_private") is not True
                or notebook_meta.get("dataset_sources") !=
                [f"{account}/paper-v2c-holdout-1000-4730d07"]):
            raise ValueError("Kaggle notebook was not private with locked input")
        provenance["shards"].append({"account": account, "codec": codec,
            "shard": shard, "dataset": notebook_meta["dataset_sources"][0],
            "notebook": notebook_meta["id"],
            "notebook_sha256": sha256(notebook_target / "notebook.ipynb"),
            "primary": hashes["primary"], "mc3": hashes["mc3"]})
    for codec in ("h264", "h265"):
        result_path = out_dir / f"{codec}_result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if (result.get("experiment") != "v2c_source_disjoint_holdout"
                or result.get("n") != 1000 or result.get("codec") != codec
                or result.get("source_fingerprint") != FINGERPRINT
                or result.get("index_sha256") != index_sha
                or result.get("preregistration_commit") != PREREG_COMMIT
                or result.get("bootstrap_seed") != SEED
                or result.get("bootstrap_draws") != DRAWS):
            raise ValueError(f"merged {codec} result changed")
        for stage in ("primary", "mc3"):
            expected_hashes = [next(row[stage]["records_sha256"]
                for row in provenance["shards"]
                if row["codec"] == codec and row["shard"] == shard)
                for shard in (0, 1)]
            if result["raw_record_sha256"][stage] != expected_hashes:
                raise ValueError("merged result raw-shard hashes differ")
        provenance["results"][codec] = sha256(result_path)
    provenance_path = out_dir / "run_provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
    checksum_path = out_dir / "SHA256SUMS.txt"
    checksum_path.write_text("".join(
        f"{sha256(path)}  {path.relative_to(out_dir).as_posix()}\n"
        for path in sorted(out_dir.rglob("*"))
        if path.is_file() and path != checksum_path),
        encoding="utf-8", newline="\n")
    print(json.dumps({"shards": len(provenance["shards"]),
                      "results": provenance["results"]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--notebook-root", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    package(args.raw_root, args.notebook_root, args.input_manifest, args.out_dir)


if __name__ == "__main__":
    main()
