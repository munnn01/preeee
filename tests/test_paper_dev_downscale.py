"""The fixed-resolution comparison remains paired and directionally explicit."""

import numpy as np

from ops import paper_dev_downscale


def test_direct_comparison_uses_each_fixed_baseline_as_anchor(monkeypatch):
    base = np.asarray([[[.5 * (.72 ** qp), float(i < 35 - 5 * qp),
                         float(i < 34 - 5 * qp)] for qp in range(5)]
                       for i in range(40)])
    selected = base.copy()
    selected[:, :, 0] *= .8
    area96 = base.copy()
    area96[:, :, 0] *= .7
    area112 = base.copy()
    area112[:, :, 0] *= .9

    monkeypatch.setattr(paper_dev_downscale, "load_frozen",
                        lambda *_args: ({}, {"policies": {"C": {"mode": "C"}}},
                                       {"mode": "C"}))
    monkeypatch.setattr(paper_dev_downscale, "prepare", lambda rows, _risk: rows)
    monkeypatch.setattr(paper_dev_downscale, "selected_arrays",
                        lambda _rows, policy: (selected if policy["mode"] == "C"
                                               else base, {}))
    monkeypatch.setattr(paper_dev_downscale, "fixed_arrays",
                        lambda _rows, name: (area96 if name == "area96"
                                              else area112, {name: 200}))
    report = paper_dev_downscale.analyze([{}] * 40, "h264", draws=8)
    first = report["direct_comparisons"]["V2-C_vs_area96"]
    second = report["direct_comparisons"]["V2-C_vs_area112"]
    assert first["analyzers"]["r2plus1d_18"]["metrics"]["bd_rate_top1_pct"] > 0
    assert second["analyzers"]["r2plus1d_18"]["metrics"]["bd_rate_top1_pct"] < 0
    assert first["bootstrap"]["r3d_18"]["bd_rate_top1_pct"]["requested_draws"] == 8
