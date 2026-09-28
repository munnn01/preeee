import numpy as np
import pytest

from ops.v7_dev_transfer import choose_v7, primary_feasible
from ops.v7_pixel_proxy import prereg_bytes_match, proxy_metrics
from ops.push_v7_pixel_proxy import payload
from src.models.codec_search import CANDIDATES


def test_pixel_proxy_identity_and_changed_temporal_signal():
    source = np.zeros((16, 128, 128, 3), dtype=np.uint8)
    source[::2, 30:90, 30:90] = 200
    identity = proxy_metrics(source, source.copy())
    unchanged = np.repeat(source[:1], 16, axis=0)
    changed = proxy_metrics(source, unchanged)
    assert identity == {"spatial": 0.0, "temporal": 0.0, "proxy": 0.0}
    assert changed["spatial"] > 0
    assert changed["temporal"] > 0
    assert changed["proxy"] == max(changed["spatial"], changed["temporal"])


def test_v7_admissibility_uses_both_primary_event_predictions():
    obs = [{"name": name, "bpp": bpp} for name, bpp in zip(
        CANDIDATES, (1.0, 0.8, 0.55, 0.95, 0.9, 0.88), strict=True)]
    proxy = {name: {"proxy": 0.0} for name in CANDIDATES}
    probabilities = np.zeros((6, 2, 2), dtype=np.float64)
    probabilities[2, 1, 0] = 0.1  # area96 looks cheap but harms r3d
    policy = {"mode": "V7_pixel", "threshold": 0.0, "pixel_weight": 0.25}
    assert choose_v7(obs, 1, probabilities, proxy, policy) == 1
    probabilities[2, 1, 0] = 0.0
    assert choose_v7(obs, 1, probabilities, proxy, policy) == 2
    with pytest.raises(ValueError):
        choose_v7(obs, 1, probabilities, proxy,
                  {"mode": "V7_pixel", "threshold": -0.1, "pixel_weight": 0.25})


def test_primary_gate_checks_each_analyzer_and_pixel_improvement():
    baseline = {name: {"metrics": {"bd_rate_top1_pct": -12.0}}
                for name in ("r2plus1d_18", "r3d_18")}
    trial = {name: {"metrics": {"bd_rate_top1_pct": -11.5,
                                "bd_accuracy_top1": 0.02,
                                "min_same_qp_top1_gap": 0.0}}
             for name in baseline}
    assert primary_feasible(trial, baseline, 0.2, 0.3)
    trial["r3d_18"]["metrics"]["bd_rate_top1_pct"] = -9.99
    assert not primary_feasible(trial, baseline, 0.2, 0.3)
    trial["r3d_18"]["metrics"]["bd_rate_top1_pct"] = -11.5
    assert not primary_feasible(trial, baseline, 0.3, 0.3)


def test_kaggle_payload_is_private_and_stage_pinned():
    book, metadata = payload("a" * 40, "shungg05", "v7-pixel-cal", "calibration")
    source = "".join(book["cells"][0]["source"])
    assert 'REF="' + "a" * 40 + '"' in source
    assert 'STAGE="calibration"' in source
    assert metadata["is_private"] is True
    assert metadata["dataset_sources"] == ["qktttttttttt/kineticscleaned"]
    with pytest.raises(ValueError):
        payload("a" * 40, "shungg05", "v7-pixel-test", "holdout")


def test_byte_pinned_plan_does_not_normalize_crlf():
    rel = "configs/v7_dev_proxy_plan.json"
    assert prereg_bytes_match(rel, b"{\r\n}\r\n", b"{\r\n}\r\n")
    assert not prereg_bytes_match(rel, b"{\n}\n", b"{\r\n}\r\n")
    assert prereg_bytes_match("docs/PREREGISTRATION_V7_TRANSFER.md",
                              b"a\r\nb\r\n", b"a\nb\n")
