"""Raw holdout packaging rejects an mc3 shard detached from its primary shard."""

import json

import pytest

from ops.package_paper_holdout_confirm import (DRAWS, FINGERPRINT,
    PREREG_COMMIT, SEED, validate_shard)


def test_mc3_shard_requires_exact_primary_hash_and_order(tmp_path):
    ids = [f"videos/{number:011d}_000000_000010.mp4" for number in range(500)]
    sources = [f"{number:011d}" for number in range(500)]
    index_sha = "a" * 64
    primary_sha = "b" * 64
    manifest = {
        "experiment": "v2c_source_disjoint_holdout",
        "stage": "independent_mc3_selected_stream",
        "codec": "h264", "shard": 0, "shards": 2, "n": 500,
        "sample_ids": ids, "source_ids": sources,
        "source_fingerprint": FINGERPRINT, "index_sha256": index_sha,
        "preregistration_commit": PREREG_COMMIT, "code_commit": PREREG_COMMIT,
        "bootstrap_seed": SEED, "bootstrap_draws": DRAWS,
        "bootstrap_unit": "source video; all QPs, arms and analyzers paired",
        "primary_records_sha256": primary_sha,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    records = [{"sequence_id": key} for key in ids]
    (tmp_path / "shard_records.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    with pytest.raises(ValueError, match="exact primary"):
        validate_shard(tmp_path, manifest["stage"], "h264", 0,
                       ids, sources, index_sha, "c" * 64)
    assert validate_shard(tmp_path, manifest["stage"], "h264", 0,
                          ids, sources, index_sha, primary_sha)["records_sha256"]
    records[0]["sequence_id"] = "videos/changed.mp4"
    (tmp_path / "shard_records.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid or incomplete"):
        validate_shard(tmp_path, manifest["stage"], "h264", 0,
                       ids, sources, index_sha, primary_sha)
