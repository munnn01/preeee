"""V10 label-free spatial gate. No labels or recognition models enter this module."""
from __future__ import annotations

from itertools import product
import math

import cv2
import numpy as np

from src.models.codec_search import CANDIDATES

QUANTILES = (0.5, 0.75, 0.9)
TAUS = (0.02, 0.05, 0.1)
SAVINGS = (0.05, 0.1, 0.2)
WEIGHTS = (0.5, 1.0, 2.0)
QPS = (30, 35, 40, 45, 50)


def gray(clip: np.ndarray) -> np.ndarray:
    if (clip.dtype != np.uint8 or clip.ndim != 4 or clip.shape[0] != 16
            or clip.shape[-1] != 3 or clip.shape[1] != clip.shape[2]
            or clip.shape[1] not in (96, 112, 128)):
        raise ValueError("expected 16-frame uint8 RGB candidate at 96/112/128 pixels")
    if clip.shape[1] != 128:
        clip = np.stack([cv2.resize(f, (128, 128), interpolation=cv2.INTER_LINEAR)
                         for f in clip])
    return np.stack([cv2.cvtColor(f, cv2.COLOR_RGB2GRAY) for f in clip]).astype(np.float64) / 255


def derivatives(y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (np.diff(y, axis=2), np.diff(y, axis=1),
            y[:, 1:-1, :-2] + y[:, 1:-1, 2:] + y[:, :-2, 1:-1]
            + y[:, 2:, 1:-1] - 4 * y[:, 1:-1, 1:-1])


def spatial_proxy(source: np.ndarray, decoded: np.ndarray) -> dict:
    """Squared gradient/Laplacian error on a shared source-pixel grid, in [0,2]."""
    if source.shape != (16, 128, 128, 3):
        raise ValueError("source reference must be 128x128")
    a, b = derivatives(gray(source)), derivatives(gray(decoded))
    energies = [float(np.mean(x * x)) for x in a]
    eg = sum(float(np.mean((a[k] - b[k]) ** 2)) for k in (0, 1)) / (
        sum(energies[:2]) + sum(float(np.mean(b[k] ** 2)) for k in (0, 1)) + 1e-12)
    el = float(np.mean((a[2] - b[2]) ** 2)) / (
        energies[2] + float(np.mean(b[2] ** 2)) + 1e-12)
    return {"complexity": sum(energies[:2]), "spatial_error": float((eg + el) / 2)}


def policy_grid(complexities: list[float]) -> list[dict]:
    values = np.asarray(complexities, dtype=np.float64)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or np.any(values < 0):
        raise ValueError("invalid CAL source complexities")
    return [{"complexity_quantile": p, "complexity_threshold": float(np.quantile(values, p, method="linear")),
             "tau": tau, "minimum_saving": g, "spatial_weight": weight}
            for p, tau, g, weight in product(QUANTILES, TAUS, SAVINGS, WEIGHTS)]


def validate_policy(policy: dict) -> None:
    expected = {"complexity_quantile", "complexity_threshold", "tau", "minimum_saving", "spatial_weight"}
    if set(policy) != expected or any(type(v) not in (float, int) or not math.isfinite(v) for v in policy.values()):
        raise ValueError("invalid policy schema or nonfinite parameter")
    if (policy["complexity_quantile"] not in QUANTILES or policy["tau"] not in TAUS
            or policy["minimum_saving"] not in SAVINGS or policy["spatial_weight"] not in WEIGHTS
            or policy["complexity_threshold"] < 0):
        raise ValueError("policy outside preregistered grid")


def choose(qp: int, complexity: float, candidates: dict, base: str, residual: str,
           policy: dict) -> tuple[str, str]:
    """Start from guarded V2-C; accept V6 only when admissibility and RD cost pass.

    The narrow schema deliberately rejects correctness, logits, predictions and labels.
    """
    validate_policy(policy)
    if (qp not in QPS or not math.isfinite(complexity) or complexity < 0
            or set(candidates) != set(CANDIDATES) or base not in CANDIDATES
            or residual not in CANDIDATES):
        raise ValueError("invalid gate inputs")
    for row in candidates.values():
        if (set(row) != {"bpp", "spatial_error"}
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in row.values())
                or row["bpp"] <= 0 or not 0 <= row["spatial_error"] <= 2):
            raise ValueError("gate accepts only finite measured bpp and spatial error")
    identity = candidates["identity128"]
    low = qp <= 35
    if low and complexity > 0 and complexity >= policy["complexity_threshold"]:
        return "identity128", "high_complexity_low_qp"
    tau, weight = policy["tau"], policy["spatial_weight"]

    def admitted(name: str) -> bool:
        if name == "identity128":
            return True
        row = candidates[name]
        excess = max(0.0, row["spatial_error"] - identity["spatial_error"])
        saving = 1 - row["bpp"] / identity["bpp"]
        return (saving >= 0 and excess <= tau * (1 if low else 2)
                and (not low or saving >= policy["minimum_saving"] + weight * excess))

    fallback = base if admitted(base) else "identity128"
    if residual != fallback and admitted(residual):
        a, b = candidates[fallback], candidates[residual]
        change = b["spatial_error"] - a["spatial_error"]
        if max(0.0, change) <= tau and math.log(b["bpp"] / a["bpp"]) + weight * change < 0:
            return residual, "v6_admitted"
    return fallback, "v2_retained" if fallback == base else "v2_guard_fallback"
