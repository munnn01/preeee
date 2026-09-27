"""Reject a source list that skips an available earlier hash-ranked ID."""
from __future__ import annotations

import pytest

from ops.lock_v4_holdout import verify_ranked_selection


def test_v4_rank_prefix_cannot_skip_available_video():
    ranked = [f"{i:011d}" for i in range(1002)]
    selected = [{"source_id": key} for key in ranked[:1000]]
    verify_ranked_selection(ranked, selected, [])
    selected[-1] = {"source_id": ranked[1000]}
    with pytest.raises(ValueError, match="deviates"):
        verify_ranked_selection(ranked, selected, [])
