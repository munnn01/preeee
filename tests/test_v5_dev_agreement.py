import copy

import numpy as np
import pytest

from ops.v5_dev_agreement import is_feasible, select_guarded
from src.models.dual_codec_search import MODELS


def _candidate(name, bpp, agreements, correct):
    return {
        "name": name,
        "bpp": bpp,
        "signals": {model: {"anchor_top1_agrees": agrees}
                    for model, agrees in zip(MODELS, agreements)},
        "correct": correct,
        "cross_correct": correct,
    }


def _policy(low=0.0, high=0.0):
    return {"mode": "P4",
            "thresholds_low": {model: low for model in MODELS},
            "thresholds_high": {model: high for model in MODELS}}


def test_agreement_guard_rejects_cheapest_disagreeing_stream_and_ignores_outcomes():
    obs = [_candidate("identity128", 1.0, (True, True), True),
           _candidate("area96", 0.4, (True, False), True),
           _candidate("area112", 0.6, (True, True), False)]
    probabilities = np.array([[0.6, 0.6], [0.8, 0.8], [0.7, 0.7]])
    assert select_guarded(obs, probabilities, 35, _policy()) == 2
    changed = copy.deepcopy(obs)
    for row in changed:
        row["correct"] = not row["correct"]
        row["cross_correct"] = not row["cross_correct"]
    assert select_guarded(changed, probabilities, 35, _policy()) == 2


def test_high_qp_threshold_and_nonfinite_probabilities_fail_closed():
    obs = [_candidate("identity128", 1.0, (True, True), True),
           _candidate("area112", 0.6, (True, True), True)]
    probabilities = np.array([[0.6, 0.6], [0.7, 0.7]])
    assert select_guarded(obs, probabilities, 40, _policy(high=0.2)) == 0
    probabilities[1, 0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        select_guarded(obs, probabilities, 35, _policy())


def test_calibration_bound_is_per_analyzer_and_inclusive_at_one_point():
    old = {model: {"metrics": {"bd_rate_top1_pct": -10.0}} for model in MODELS}
    trial = {model: {"metrics": {"bd_rate_top1_pct": -9.0,
                                 "bd_accuracy_top1": 0.01,
                                 "min_same_qp_top1_gap": -0.01}}
             for model in MODELS}
    assert is_feasible(trial, old)
    trial[MODELS[1]]["metrics"]["bd_rate_top1_pct"] = -8.99
    assert not is_feasible(trial, old)
