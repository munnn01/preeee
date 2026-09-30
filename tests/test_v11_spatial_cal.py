from __future__ import annotations

import numpy as np
import pytest
import torch

from ops.v11_spatial_cal import feasible, measured_names, rank_key
from ops.v11_spatial_policy import QP_SETS, choose, distance, grid, prepared
from src.tasks.action_recognition import ActionRecognitionAnalyzer, _MEAN, _STD


def test_proxy_matches_analyzer_input_grid_without_model_weights():
    rng = np.random.default_rng(12)
    for side in (96, 112, 128):
        clip = rng.integers(0, 256, (16, side, side, 3), dtype=np.uint8)
        analyzer = ActionRecognitionAnalyzer.__new__(ActionRecognitionAnalyzer)
        torch.nn.Module.__init__(analyzer)
        analyzer.clip_size = 112
        analyzer.register_buffer("mean", torch.tensor(_MEAN).view(1, 3, 1, 1, 1))
        analyzer.register_buffer("std", torch.tensor(_STD).view(1, 3, 1, 1, 1))
        tensor = torch.from_numpy(clip.transpose(3, 0, 1, 2).copy())[None].float() / 255
        actual = analyzer._prep(tensor)[0].permute(1, 0, 2, 3)
        assert torch.allclose(prepared(clip), actual, atol=1e-6, rtol=0)


def test_proxy_identity_and_spatial_change():
    source = np.zeros((16, 128, 128, 3), dtype=np.uint8)
    source[:, :, 64:] = 220
    altered = source.copy()
    altered[:, :, 64:] = 80
    assert distance(source, source) == 0
    assert 0 < distance(source, altered) <= 2


def test_policy_uses_only_frozen_choices_and_strict_threshold():
    fixed = {"qp": 40, "v2": "area112", "v6": "area96"}
    candidates = {"identity128": {"bpp": 1.0, "d112": 0.05},
                  "area112": {"bpp": 0.8, "d112": 0.10},
                  "area96": {"bpp": 0.79, "d112": 0.16}}
    assert choose(40, fixed, candidates, {"tau": 0.05, "slack": 0.02, "qp_mode": "all"})[0] == "area112"
    assert choose(40, fixed, candidates, {"tau": 0.05, "slack": 0, "qp_mode": "all"})[0] == "area96"
    assert choose(40, fixed, candidates, {"tau": 0.05, "slack": 0.02, "qp_mode": "low"})[0] == "area96"
    with pytest.raises(ValueError):
        choose(40, fixed, {**candidates, "label": {"bpp": 1.0, "d112": 0.0}},
               {"tau": 0.0, "slack": 0.02, "qp_mode": "all"})
    assert measured_names(fixed) == set(candidates)


def test_grid_and_primary_guard_are_fixed():
    assert len(grid()) == 36
    assert set(QP_SETS) == {"low", "lowmid", "all"}
    baseline = {m: {"metrics": {"bd_rate_top1_pct": -14.0}} for m in ("r2plus1d_18", "r3d_18")}
    report = {m: {"metrics": {"bd_rate_top1_pct": -13.2, "bd_accuracy_top1": 0.02,
                              "min_same_qp_top1_gap": -0.005}}
              for m in baseline}
    assert feasible(report, baseline, 0.001)
    assert not feasible(report, baseline, 1e-6)
    report["r3d_18"]["metrics"]["bd_rate_top1_pct"] = -12.9
    assert not feasible(report, baseline, 0.001)


def test_rank_prefers_proxy_reduction_then_rate():
    analyzers = {m: {"metrics": {"bd_rate_top1_pct": -12}} for m in ("r2plus1d_18", "r3d_18")}
    def row(reduction):
        return {"policy": {"tau": 0.0, "slack": 0.0, "qp_mode": "low"},
                "mean_d112_reduction": reduction, "analyzers": analyzers, "switch_count": 5}
    assert rank_key(row(0.2)) < rank_key(row(0.1))
