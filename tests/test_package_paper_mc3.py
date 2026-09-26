"""Fail-closed provenance checks for the old-TEST mc3 package."""

import json

import pytest

from ops.package_paper_mc3 import fingerprint, validate_mc3


def _bundle(tmp_path):
    ids = [f"class/video-{i:04d}.mp4" for i in range(1000)]
    fp = fingerprint(ids)
    manifests = []
    for shard in (0, 1):
        shard_ids = ids[500 * shard:500 * (shard + 1)]
        directory = tmp_path / "h264" / f"shard_{shard}"
        directory.mkdir(parents=True)
        manifest = {"shard": shard, "n": 500, "sample_ids": shard_ids,
                    "shard_fingerprint": fingerprint(shard_ids),
                    "test_fingerprint": fp, "code_commit": "commit",
                    "config_sha256": "config", "index_sha256": "index",
                    "frozen_policy_sha256": "policy", "risk_sha256": "risk"}
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (directory / "shard_records.jsonl").write_text("".join(
            json.dumps({"sequence_id": key}) + "\n" for key in shard_ids),
            encoding="utf-8")
        manifests.append(manifest)
    source = {"experiment": "dual_v2_heldout_mc3", "codec": "h264",
              "split": "previously_inspected_test", "fingerprint": fp,
              "source_manifests": manifests,
              "result": {"n": 1000, "model": "mc3_18", "bootstrap": {
                  key: {"requested_draws": 2000}
                  for key in ("bd_rate_top1_pct", "bd_accuracy_top1_pp")}}}
    return source, fp


def test_mc3_package_accepts_exact_two_shards(tmp_path):
    source, fp = _bundle(tmp_path)
    evidence = validate_mc3(source, "h264", fp, tmp_path)
    assert [item["shard"] for item in evidence] == [0, 1]
    assert all(len(item["records_sha256"]) == 64 for item in evidence)


def test_mc3_package_rejects_source_overlap(tmp_path):
    source, fp = _bundle(tmp_path)
    source["source_manifests"][1]["sample_ids"][0] = (
        source["source_manifests"][0]["sample_ids"][0])
    with pytest.raises(ValueError, match="manifest differs"):
        validate_mc3(source, "h264", fp, tmp_path)


def test_mc3_package_rejects_wrong_bootstrap_count(tmp_path):
    source, fp = _bundle(tmp_path)
    source["result"]["bootstrap"]["bd_rate_top1_pct"]["requested_draws"] = 200
    with pytest.raises(ValueError, match="draw count"):
        validate_mc3(source, "h264", fp, tmp_path)
