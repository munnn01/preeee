#!/usr/bin/env python
"""Audit and package the existing mc3 replication on the old V2 TEST set.

The numerical mc3 result must first be regenerated with
``python -m ops.paper_heldout_mc3 merge`` from the two raw 500-video shards.
This script compares that regenerated file byte-for-byte with the historical
merged file, then adds provenance without changing its measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs/dual_codec_search_v2_confirm_1000.json"
OLD_V2 = REPO / "results/dual_codec_search_v2_confirm_1000"
CODECS = ("h264", "h265")
MODELS = ("r2plus1d_18", "r3d_18", "mc3_18")
BOOTSTRAP_SEED = 20260924


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()[:16]


def validate_mc3(source: dict, codec: str, expected_fingerprint: str,
                 shard_root: Path) -> list[dict]:
    if (source.get("experiment") != "dual_v2_heldout_mc3"
            or source.get("codec") != codec
            or source.get("split") != "previously_inspected_test"
            or source.get("fingerprint") != expected_fingerprint
            or source.get("result", {}).get("n") != 1000
            or source["result"].get("model") != "mc3_18"):
        raise ValueError(f"invalid historical mc3 result for {codec}")
    manifests = source.get("source_manifests", [])
    if len(manifests) != 2 or [m.get("shard") for m in manifests] != [0, 1]:
        raise ValueError("mc3 needs two ordered shards")
    all_ids: list[str] = []
    provenance = []
    for manifest in manifests:
        directory = shard_root / codec / f"shard_{manifest['shard']}"
        manifest_path = directory / "manifest.json"
        records_path = directory / "shard_records.jsonl"
        disk_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if disk_manifest != manifest:
            raise ValueError("mc3 shard manifest differs from merged report")
        rows = [json.loads(line) for line in records_path.read_text(
            encoding="utf-8").splitlines()]
        ids = [row["sequence_id"] for row in rows]
        if (len(rows) != 500 or manifest["n"] != 500
                or ids != manifest["sample_ids"]
                or fingerprint(ids) != manifest["shard_fingerprint"]):
            raise ValueError("incomplete or reordered mc3 shard")
        all_ids.extend(ids)
        provenance.append({"shard": manifest["shard"],
                           "manifest_sha256": sha256(manifest_path),
                           "records_sha256": sha256(records_path)})
    if len(set(all_ids)) != 1000 or fingerprint(all_ids) != expected_fingerprint:
        raise ValueError("mc3 merged source-video fingerprint mismatch")
    for key in ("code_commit", "config_sha256", "index_sha256",
                "test_fingerprint", "frozen_policy_sha256", "risk_sha256"):
        if manifests[0][key] != manifests[1][key]:
            raise ValueError(f"mc3 shard provenance mismatch: {key}")
    if manifests[0]["test_fingerprint"] != expected_fingerprint:
        raise ValueError("mc3 manifest TEST fingerprint mismatch")
    bootstrap = source["result"]["bootstrap"]
    for metric in ("bd_rate_top1_pct", "bd_accuracy_top1_pp"):
        if bootstrap[metric]["requested_draws"] != 2000:
            raise ValueError("mc3 bootstrap draw count changed")
    return provenance


def validate_v2(report: dict, codec: str, expected_fingerprint: str) -> None:
    if (report.get("codec") != codec or report.get("n") != 1000
            or report.get("test_fingerprint") != expected_fingerprint
            or report.get("split") != "test"):
        raise ValueError("V2 replication report does not match mc3 sample")
    if set(report["arms"]["dual_v2"]["analyzers"]) != set(MODELS[:2]):
        raise ValueError("missing V2 analyzer")
    for model in MODELS[:2]:
        draw = report["arms"]["dual_v2"]["bootstrap"][model]
        if draw["bd_rate_top1_pct"]["requested_draws"] != 2000:
            raise ValueError("V2 bootstrap draw count changed")


def package(source_dir: Path, remerged_dir: Path, shard_root: Path,
            out_dir: Path, audit_commit: str) -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    expected_fingerprint = config["test_fingerprint"]
    out_dir.mkdir(parents=True, exist_ok=True)
    combined = {"scope": "replication on previously inspected V1/V2 TEST",
                "test_fingerprint": expected_fingerprint,
                "n_source_videos": 1000, "bootstrap_unit": "source video",
                "bootstrap_draws": 2000, "bootstrap_seed": BOOTSTRAP_SEED,
                "audit_code_commit": audit_commit, "rows": []}
    for codec in CODECS:
        original_path = source_dir / f"{codec}_mc3_result.json"
        remerged_path = remerged_dir / f"{codec}_mc3_remerged.json"
        if original_path.read_bytes() != remerged_path.read_bytes():
            raise ValueError(f"regenerated {codec} mc3 JSON differs byte-for-byte")
        source = json.loads(original_path.read_text(encoding="utf-8"))
        shard_provenance = validate_mc3(source, codec, expected_fingerprint,
                                        shard_root)
        for item in shard_provenance:
            shard = item["shard"]
            raw_dir = out_dir / "raw" / codec / f"shard_{shard}"
            raw_dir.mkdir(parents=True, exist_ok=True)
            source_shard = shard_root / codec / f"shard_{shard}"
            for filename, hash_key in (("manifest.json", "manifest_sha256"),
                                       ("shard_records.jsonl", "records_sha256")):
                copied = raw_dir / filename
                shutil.copyfile(source_shard / filename, copied)
                if sha256(copied) != item[hash_key]:
                    raise ValueError("copied raw mc3 record differs from source")
            item["committed_raw_dir"] = str(raw_dir.relative_to(out_dir)).replace("\\", "/")
        v2_path = OLD_V2 / f"{codec}_result.json"
        v2 = json.loads(v2_path.read_text(encoding="utf-8"))
        validate_v2(v2, codec, expected_fingerprint)
        manifest = source["source_manifests"][0]
        packaged = dict(source)
        packaged["provenance"] = {
            "scope": "old TEST replication; not an independent data holdout",
            "source_merged_sha256": sha256(original_path),
            "source_shards": shard_provenance,
            "source_code_commit": manifest["code_commit"],
            "audit_code_commit": audit_commit,
            "config_sha256": manifest["config_sha256"],
            "index_sha256": manifest["index_sha256"],
            "v2_result_sha256": sha256(v2_path),
            "bootstrap_unit": "source video; all QPs paired",
            "bootstrap_draws": 2000,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "dataset_fingerprint": expected_fingerprint,
        }
        output_path = out_dir / f"{codec}_result.json"
        output_path.write_text(json.dumps(packaged, indent=2, allow_nan=False)
                               + "\n", encoding="utf-8")
        for model in MODELS:
            if model == "mc3_18":
                metrics = source["result"]["metrics"]
                bootstrap = source["result"]["bootstrap"]
            else:
                analyzer = v2["arms"]["dual_v2"]["analyzers"][model]
                metrics = analyzer["metrics"]
                bootstrap = v2["arms"]["dual_v2"]["bootstrap"][model]
            combined["rows"].append({"codec": codec, "analyzer": model,
                "metrics": metrics, "bootstrap": bootstrap,
                "result_file": output_path.name if model == "mc3_18"
                else str(v2_path.relative_to(REPO)).replace("\\", "/"),
                "result_sha256": sha256(output_path) if model == "mc3_18"
                else sha256(v2_path)})
    combined_path = out_dir / "combined_old_test.json"
    combined_path.write_text(json.dumps(combined, indent=2, allow_nan=False)
                             + "\n", encoding="utf-8")
    checksum_path = out_dir / "SHA256SUMS.txt"
    checksum_path.write_text("".join(
        f"{sha256(path)}  {path.relative_to(out_dir).as_posix()}\n"
        for path in sorted(out_dir.rglob("*"))
        if path.is_file() and path != checksum_path), encoding="utf-8")
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--remerged-dir", type=Path, required=True)
    parser.add_argument("--shard-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "-c",
        f"safe.directory={REPO.as_posix()}", "rev-parse", "HEAD"], cwd=REPO,
                                     text=True).strip()
    report = package(args.source_dir, args.remerged_dir, args.shard_root,
                     args.out_dir, commit)
    print(json.dumps({"scope": report["scope"], "rows": len(report["rows"])}))


if __name__ == "__main__":
    main()
