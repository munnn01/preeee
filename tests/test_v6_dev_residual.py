import copy

import numpy as np
import pytest

from ops.v6_dev_residual import (THRESHOLDS, WEIGHTS, is_feasible, pair_features,
                                 policy_grid, predicted_measurements,
                                 select_residual)
from src.models.codec_search import CANDIDATES
from src.models.dual_codec_search import MODELS, SIGNALS, observations


def candidate(name, bpp, distance, correct=False):
    signals = {model: {key: 0.0 for key in SIGNALS} for model in MODELS}
    for model in MODELS:
        signals[model]["feature_distance"] = distance
    return {"name": name, "bpp": bpp, "signals": signals,
            "correct": correct, "cross_correct": not correct}


def test_grid_is_locked_and_pair_features_exclude_outcomes():
    grid = policy_grid()
    assert len(grid) == 12
    assert {(p["minimum_expected_delta"], p["feature_weight"]) for p in grid} == {
        (threshold, weight) for threshold in THRESHOLDS for weight in WEIGHTS}
    rows = [candidate("identity128", 1.0, 0.1, True),
            candidate("area112", 0.8, 0.2, False)]
    obs = observations(rows)
    before = pair_features(obs, 1, 0, 35)
    assert before.shape == (82,)
    for row in rows:
        row["correct"] = not row["correct"]
        row["cross_correct"] = not row["cross_correct"]
    assert np.array_equal(before, pair_features(observations(rows), 1, 0, 35))


def test_selector_can_pay_rate_to_reduce_feature_loss_without_reading_labels():
    rows = [candidate("identity128", 1.0, 0.1, True),
            candidate("area112", 0.5, 0.3, False),
            candidate("area96", 0.3, 0.4, True)]
    obs = observations(rows)
    probabilities = np.zeros((3, 2, 2))
    probabilities[0, :, 0] = 0.01
    probabilities[0, :, 1] = 0.02
    probabilities[2, :, 0] = 0.1
    assert select_residual(obs, 1, probabilities,
                           {"mode": "V6", "minimum_expected_delta": 0.0,
                            "feature_weight": 80.0}) == 0
    assert select_residual(obs, 1, probabilities,
                           {"mode": "V6", "minimum_expected_delta": 0.0,
                            "feature_weight": 0.0}) == 1
    # If the identity's expected change is too harmful, V2-C remains available.
    probabilities[0, :, 0] = 0.4
    assert select_residual(obs, 1, probabilities,
                           {"mode": "V6", "minimum_expected_delta": 0.0,
                            "feature_weight": 80.0}) == 1
    changed = copy.deepcopy(rows)
    for row in changed:
        row["correct"] = not row["correct"]
    assert observations(changed) == obs
    with pytest.raises(ValueError, match="grid"):
        select_residual(obs, 1, probabilities,
                        {"mode": "V6", "minimum_expected_delta": -0.5,
                         "feature_weight": 80.0})


def test_prediction_event_axes_and_baseline_zero(monkeypatch):
    rows = [candidate(name, 1.0 - i / 10, 0.1 + i / 100)
            for i, name in enumerate(CANDIDATES)]
    measurements = [{"qp": qp, "candidates": rows}
                    for qp in (30, 35, 40, 45, 50)]
    monkeypatch.setattr("ops.v6_dev_residual.risk_scores",
                        lambda obs, qp, risk: np.zeros((len(obs), 2)))
    models = {MODELS[0]: {"harm": {"constant": 0.1}, "gain": {"constant": 0.9}},
              MODELS[1]: {"harm": {"constant": 0.2}, "gain": {"constant": 0.8}}}
    prepared = predicted_measurements([{"measurements": measurements}], {},
                                      {"mode": "identity"}, models)
    _, _, baseline, probability = prepared[0][0]
    assert baseline == 0
    assert np.array_equal(probability[0], np.zeros((2, 2)))
    assert np.allclose(probability[1], [[0.1, 0.9], [0.2, 0.8]])


def test_calibration_bound_is_per_analyzer_and_proxy_must_improve():
    old = {model: {"metrics": {"bd_rate_top1_pct": -10.0}} for model in MODELS}
    trial = {model: {"metrics": {"bd_rate_top1_pct": -9.0,
                                 "bd_accuracy_top1": 0.01,
                                 "min_same_qp_top1_gap": -0.01}}
             for model in MODELS}
    assert is_feasible(trial, old, 0.199, 0.2)
    assert not is_feasible(trial, old, 0.2, 0.2)
    trial[MODELS[1]]["metrics"]["bd_rate_top1_pct"] = -8.99
    assert not is_feasible(trial, old, 0.199, 0.2)
