"""Reject a source list that skips an available earlier hash-ranked ID."""
from __future__ import annotations

import pytest

from ops.lock_v4_holdout import matches_locked_metadata, verify_ranked_selection


def test_v4_rank_prefix_cannot_skip_available_video():
    ranked = [f"{i:011d}" for i in range(1002)]
    selected = [{"source_id": key} for key in ranked[:1000]]
    verify_ranked_selection(ranked, selected, [])
    selected[-1] = {"source_id": ranked[1000]}
    with pytest.raises(ValueError, match="deviates"):
        verify_ranked_selection(ranked, selected, [])


def test_v4_preflight_metadata_changes_only_status():
    locked = {"status": "metadata_only", "source": "official", "target": 1000}
    preflight = {**locked, "status": "preflight", "complete": True}
    assert matches_locked_metadata(preflight, locked)
    assert not matches_locked_metadata({**preflight, "target": 999}, locked)
    assert not matches_locked_metadata({**preflight, "status": "other"}, locked)
