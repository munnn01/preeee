"""V11 label-free spatial distance at the analyzers' 112-pixel input grid."""
from __future__ import annotations

from itertools import product
import math

import numpy as np
import torch
import torch.nn.functional as F

from src.models.codec_search import CANDIDATES

QPS = (30, 35, 40, 45, 50)
TAUS = (0.0, 0.01, 0.025, 0.05)
SLACKS = (0.0, 0.02, 0.05)
QP_SETS = {"low": (30, 35), "lowmid": (30, 35, 40), "all": QPS}
MEAN = (0.43216, 0.394666, 0.37645)
STD = (0.22803, 0.22145, 0.216989)


def prepared(clip: np.ndarray) -> torch.Tensor:
    """Replicate ActionRecognitionAnalyzer._prep without constructing an analyzer."""
    if (clip.dtype != np.uint8 or clip.ndim != 4 or clip.shape[0] != 16
            or clip.shape[-1] != 3 or clip.shape[1] != clip.shape[2]
            or clip.shape[1] not in (96, 112, 128)):
        raise ValueError("expected sixteen uint8 RGB frames at 96/112/128 pixels")
    x = torch.from_numpy(np.ascontiguousarray(clip.transpose(0, 3, 1, 2))).float().div_(255)
    if x.shape[-1] != 112:
        x = F.interpolate(x, size=(112, 112), mode="bilinear", align_corners=False)
    mean = x.new_tensor(MEAN).view(1, 3, 1, 1)
    std = x.new_tensor(STD).view(1, 3, 1, 1)
    return (x - mean) / std


def derivatives(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    return (x[..., 1:] - x[..., :-1], x[..., 1:, :] - x[..., :-1, :],
            x[..., 1:-1, :-2] + x[..., 1:-1, 2:]
            + x[..., :-2, 1:-1] + x[..., 2:, 1:-1] - 4 * x[..., 1:-1, 1:-1])


def distance(source: np.ndarray, decoded: np.ndarray) -> float:
    if source.shape != (16, 128, 128, 3):
        raise ValueError("source must use the frozen 128-pixel grid")
    a, b = derivatives(prepared(source)), derivatives(prepared(decoded))
    numerator_g = sum(float(torch.mean((a[k] - b[k]) ** 2)) for k in (0, 1))
    denominator_g = sum(float(torch.mean(t ** 2)) for k in (0, 1) for t in (a[k], b[k])) + 1e-12
    numerator_l = float(torch.mean((a[2] - b[2]) ** 2))
    denominator_l = float(torch.mean(a[2] ** 2) + torch.mean(b[2] ** 2)) + 1e-12
    value = (numerator_g / denominator_g + numerator_l / denominator_l) / 2
    if not math.isfinite(value) or not 0 <= value <= 2 + 1e-6:
        raise ValueError("invalid analyzer-grid distance")
    return min(2.0, value)


def grid() -> list[dict]:
    return [{"tau": tau, "slack": slack, "qp_mode": mode}
            for tau, slack, mode in product(TAUS, SLACKS, QP_SETS)]


def validate_policy(policy: dict) -> None:
    if (set(policy) != {"tau", "slack", "qp_mode"}
            or type(policy["tau"]) not in (float, int)
            or type(policy["slack"]) not in (float, int)
            or policy["tau"] not in TAUS or policy["slack"] not in SLACKS
            or policy["qp_mode"] not in QP_SETS):
        raise ValueError("policy outside locked V11 grid")


def choose(qp: int, fixed: dict, candidates: dict, policy: dict) -> tuple[str, str]:
    """Select only between the frozen V6 and V2-C streams."""
    validate_policy(policy)
    if qp not in QPS or fixed["qp"] != qp or fixed["v2"] not in CANDIDATES or fixed["v6"] not in CANDIDATES:
        raise ValueError("invalid frozen choice or QP")
    base, alternate = fixed["v6"], fixed["v2"]
    expected = {"identity128", base, alternate}
    if set(candidates) != expected:
        raise ValueError("missing measured candidate")
    for item in candidates.values():
        if (set(item) != {"bpp", "d112"}
                or any(type(v) not in (float, int) or not math.isfinite(v) for v in item.values())
                or item["bpp"] <= 0 or not 0 <= item["d112"] <= 2):
            raise ValueError("invalid measured rate or distance")
    if alternate == base or qp not in QP_SETS[policy["qp_mode"]]:
        return base, "v6_retained"
    a, b = candidates[base], candidates[alternate]
    if (a["d112"] - b["d112"] > policy["tau"]
            and b["bpp"] <= (1 + policy["slack"]) * a["bpp"]
            and b["bpp"] <= candidates["identity128"]["bpp"]):
        return alternate, "v2_spatial_rescue"
    return base, "v6_retained"
