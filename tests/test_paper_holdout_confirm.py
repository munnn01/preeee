"""The new holdout runner retains the original strict gate and Git lock."""

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
