"""The new holdout runner retains the original strict gate and Git lock."""

import json

import pytest

from ops import paper_holdout_confirm as confirm


def _points(rate_a, rate_b, accuracy_a=1.0, accuracy_b=1.0):
    return {name: {"metrics": {"bd_rate_top1_pct": rate,
                                "bd_accuracy_top1_pp": accuracy}}
            for name, rate, accuracy in zip(
                confirm.MODELS, (rate_a, rate_b),
                (accuracy_a, accuracy_b))}


def test_gate_is_strict_for_both_models_and_accuracy():
    assert confirm.gate_this_codec(_points(-15.001, -15.001))
    assert not confirm.gate_this_codec(_points(-15.0, -16.0))
    assert not confirm.gate_this_codec(_points(-16.0, -15.0))
    assert not confirm.gate_this_codec(_points(-16.0, -16.0, 0.0, 1.0))
    assert not confirm.gate_this_codec(_points(None, -16.0))


def test_draft_preregistration_blocks_model_evaluation(tmp_path, monkeypatch):
    repo = tmp_path
    (repo / "docs").mkdir()
    (repo / "docs/PREREGISTRATION.md").write_bytes(b"draft\r\n")
    (repo / "docs/HOLDOUT_SPLIT.md").write_bytes(b"split\r\n")
    index = repo / "index.json"
    index.write_bytes(b"{}")
    monkeypatch.setattr(confirm, "REPO", repo)
    monkeypatch.setattr(confirm.subprocess, "run", lambda *args, **kwargs: None)
    blobs = {"docs/PREREGISTRATION.md": b"draft\n",
             "docs/HOLDOUT_SPLIT.md": b"split\n",
             "configs/holdout_source_audit/index.json": b"{}"}
    monkeypatch.setattr(confirm, "git", lambda command, spec:
                        blobs[spec.split(":", 1)[1]])
    with pytest.raises(ValueError, match="not frozen in Git"):
        confirm.ready_index(index, "a" * 40)


def test_merger_requires_both_shards_and_restores_locked_video_order(tmp_path):
    ids = [f"video/{number:04d}.mp4" for number in range(1000)]
    sources = [f"{number:011d}" for number in range(1000)]
    expected = {"all_sample_ids": ids, "all_source_ids": sources,
                "index_sha256": "a" * 64,
                "preregistration_commit": "b" * 40,
                "source_fingerprint": "c" * 64,
                "policy_digest": "d" * 64,
                "config_sha256_lf": "e" * 64,
                "bootstrap_seed": 20260924, "bootstrap_draws": 2000}
    paths = [tmp_path / "shard_0", tmp_path / "shard_1"]
    for shard, path in enumerate(paths):
        path.mkdir()
        manifest = {**expected, "experiment": "v2c_source_disjoint_holdout",
                    "stage": "primary_six_candidate", "codec": "h264",
                    "shard": shard, "sample_ids": ids[shard::2],
                    "source_ids": sources[shard::2]}
        (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (path / "shard_records.jsonl").write_text("".join(
            json.dumps({"sequence_id": key}) + "\n" for key in ids[shard::2]),
            encoding="utf-8")
    rows, _ = confirm.merged_rows(paths, "primary_six_candidate", "h264", expected)
    assert [row["sequence_id"] for row in rows] == ids
    with pytest.raises(ValueError, match="incomplete or mismatched"):
        confirm.merged_rows(paths[::-1], "primary_six_candidate", "h264", expected)
