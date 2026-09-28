"""Tests for independent mc3 arms and label-free frozen stream selection."""
import numpy as np

from ops import paper_holdout_v6 as holdout


def test_mc3_curve_uses_requested_arm_without_shard_averaging():
    rows = []
    for source in range(3):
        measurements = []
        for qp in holdout.QPS:
            measurements.append({
                "qp": qp,
                "identity": {"bpp": float(100 - qp), "correct": source != 0},
                "v2": {"bpp": float(95 - qp), "correct": source != 0},
                "v6": {"bpp": float(90 - qp), "correct": source == 2},
            })
        rows.append({"measurements": measurements})
    curve = holdout.mc3_curve(rows, "v6")
    assert curve["30"] == {"n": 3, "bpp": 60.0, "top1": 1 / 3}
    assert holdout.mc3_curve(rows, "v2")["30"]["top1"] == 2 / 3


def test_selected_names_uses_frozen_prediction_and_not_correctness(monkeypatch):
    candidate = [{"name": "identity128"}, {"name": "area112"}]
    row = {"measurements": [{"qp": 30, "candidates": candidate}]}
    monkeypatch.setattr(holdout, "predicted_measurements",
                        lambda rows, *_: [[(row["measurements"][0],
                                            candidate, 1, np.zeros((2, 2, 2)))]] )
    monkeypatch.setattr(holdout, "select_residual", lambda *_: 0)
    assert holdout.selected_names(row, {}, {}, {}, {}) == [
        ("area112", "identity128")]
