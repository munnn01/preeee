"""The new selector must obey the locked grid and never inspect outcomes."""

import numpy as np
import pytest

from ops.v3_dev_policy import (policy_grid, select_v3, source_id, thresholds)
from src.models.dual_codec_search import MODELS, SIGNALS, observations


def candidate(name, bpp, correct):
    signals = {model: {key: 0.0 for key in SIGNALS} for model in MODELS}
    for model in MODELS:
        signals[model]["source_confidence"] = .5
        signals[model]["source_top1_agrees"] = True
    return {"name": name, "bpp": bpp, "signals": signals,
            "correct": correct, "cross_correct": not correct}


def test_grid_is_locked_and_contains_v2_c_thresholds():
    grid = policy_grid()
    assert len(grid) == len({thresholds(policy) for policy in grid}) == 81
    assert (.1, .1, .2, .2) in {thresholds(policy) for policy in grid}
    assert all(policy["mode"] == "C3" for policy in grid)


def test_selection_uses_both_analyzer_risks_and_not_outcome_fields():
    rows = [candidate("identity128", 1.0, False),
            candidate("area112", .8, True),
            candidate("area96", .6, False)]
    obs = observations(rows)
    assert all("correct" not in row and "cross_correct" not in row for row in obs)
    policy = next(p for p in policy_grid() if thresholds(p) == (.1, .1, .2, .2))
    risks = np.zeros((3, 2))
    risks[2, 1] = .15
    assert select_v3(obs, 30, risks, policy) == 1  # r3 low-QP threshold rejects area96
    assert select_v3(obs, 40, risks, policy) == 2  # high-QP threshold admits it
    rows[1]["correct"] = False
    rows[2]["correct"] = True
    assert observations(rows) == obs
    assert select_v3(observations(rows), 30, risks, policy) == 1
    risks[1, 0] = np.nan
    assert select_v3(obs, 30, risks, policy) == 0


def test_source_id_is_strict():
    assert source_id("videos/7BRpke5X7iI_000024_000034.mp4") == "7BRpke5X7iI"
    with pytest.raises(ValueError, match="cannot identify source"):
        source_id("holdout/ambiguous.mp4")
