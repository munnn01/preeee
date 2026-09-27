"""V4 confirmation keeps source pairing and label-free stream selection."""
from __future__ import annotations

import json

import numpy as np
import pytest

from ops import paper_holdout_v4 as confirm
from src.models.dual_codec_search import MODELS, SIGNALS


class _FixedProbability:
    def __init__(self, values):
        self.values = np.asarray(values)

    def predict_proba(self, features):
        assert features.shape == (3, 41)
        return np.column_stack((1 - self.values, self.values))


def _candidate(name, bpp, outcome):
    return {"name": name, "bpp": bpp,
            "signals": {model: {key: 0.0 for key in SIGNALS}
                        for model in MODELS},
            "correct": outcome, "cross_correct": not outcome}


def test_v4_mc3_choice_excludes_outcome_fields():
    item = {"qp": 40, "candidates": [
        _candidate("identity128", 1.0, True),
        _candidate("area112", .8, False),
        _candidate("area96", .6, True)]}
    policy = {"mode": "P4", "thresholds_low": dict.fromkeys(MODELS, 0.0),
              "thresholds_high": dict.fromkeys(MODELS, -0.05)}
    models = {name: _FixedProbability([.8, .81, .78]) for name in MODELS}
    assert confirm.v4_selected_index(item, models, policy) == 2
    for candidate in item["candidates"]:
        candidate["correct"] = not candidate["correct"]
        candidate["cross_correct"] = not candidate["cross_correct"]
    assert confirm.v4_selected_index(item, models, policy) == 2


def test_v4_merger_requires_two_paired_shards(tmp_path):
    ids = [f"video/{number:04d}.mp4" for number in range(1000)]
    sources = [f"{number:011d}" for number in range(1000)]
    expected = {"all_sample_ids": ids, "all_source_ids": sources,
                "index_sha256": "a" * 64,
                "preregistration_commit": "b" * 40,
                "source_fingerprint": "c" * 64,
                "policy_digest": "d" * 64,
                "freeze_manifest_sha256": "e" * 64,
                "model_sha256": dict.fromkeys(MODELS, "f" * 64),
                "bootstrap_seed": 20260928, "bootstrap_draws": 2000}
    paths = [tmp_path / "shard_0", tmp_path / "shard_1"]
    for shard, path in enumerate(paths):
        path.mkdir()
        manifest = {**expected, "experiment": confirm.EXPERIMENT,
                    "stage": "primary_six_candidate", "codec": "h264",
                    "shard": shard, "sample_ids": ids[shard::2],
                    "source_ids": sources[shard::2]}
        (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (path / "shard_records.jsonl").write_text("".join(
            json.dumps({"sequence_id": key}) + "\n" for key in ids[shard::2]),
            encoding="utf-8")
    rows, _ = confirm.merged_rows(paths, "primary_six_candidate", "h264", expected)
    assert [row["sequence_id"] for row in rows] == ids
    with pytest.raises(ValueError, match="mismatched"):
        confirm.merged_rows(paths[::-1], "primary_six_candidate", "h264", expected)


def test_v4_mc3_bootstrap_uses_new_locked_seed(monkeypatch):
    monkeypatch.setattr(confirm, "DRAWS", 3)
    rows = []
    for video in range(10):
        measurements = []
        for position, qp in enumerate(confirm.QPS):
            correct = video < 9 - position
            measurements.append({"qp": qp,
                                 "anchor": {"bpp": .4 - position * .05,
                                            "correct": correct},
                                 "trial": {"bpp": .32 - position * .04,
                                           "correct": correct}})
        rows.append({"measurements": measurements})
    result = confirm.summarize_mc3_v4(rows)
    assert result["bootstrap_seed"] == 20260928
    assert result["bootstrap"]["bd_rate_top1_pct"]["requested_draws"] == 3
    assert result["metrics"]["bd_rate_top1_pct"] < 0
