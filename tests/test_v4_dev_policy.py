"""V4 label-free selection and prespecified threshold grid."""

import numpy as np
import pytest

from ops.v4_dev_policy import MODEL_PARAMS, policy_grid, select_probability, threshold_tuple
from src.models.dual_codec_search import MODELS, SIGNALS, observations


def candidate(name, bpp, outcome):
    signals = {model: {key: 0.0 for key in SIGNALS} for model in MODELS}
    return {"name": name, "bpp": bpp, "signals": signals,
            "correct": outcome, "cross_correct": not outcome}


def test_grid_has_exactly_81_distinct_locked_thresholds():
    grid = policy_grid()
    assert len(grid) == len({threshold_tuple(policy) for policy in grid}) == 81
    assert all(set(threshold_tuple(policy)) <= {-.05, 0., .05} for policy in grid)
    assert MODEL_PARAMS["early_stopping"] is False
    assert MODEL_PARAMS["random_state"] == 53


def test_selector_uses_predicted_correctness_and_never_outcome_fields():
    rows = [candidate("identity128", 1.0, True),
            candidate("area112", .8, False),
            candidate("area96", .6, True)]
    obs = observations(rows)
    assert all("correct" not in row and "cross_correct" not in row for row in obs)
    policy = next(p for p in policy_grid()
                  if threshold_tuple(p) == (0., 0., -.05, 0.))
    probabilities = np.array([[.80, .80], [.81, .81], [.78, .80]])
    assert select_probability(obs, probabilities, 30, policy) == 1
    assert select_probability(obs, probabilities, 40, policy) == 2
    rows[1]["correct"] = True
    rows[2]["correct"] = False
    assert observations(rows) == obs
    assert select_probability(observations(rows), probabilities, 30, policy) == 1
    probabilities[1, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        select_probability(obs, probabilities, 30, policy)
