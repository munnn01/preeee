"""Read only the exact DEV-selected H.265 V6 files for a new holdout."""
from __future__ import annotations

import json
import subprocess

import joblib

from ops.dual_codec_search import digest
from ops.prepare_official_holdout import REPO, sha256
from ops.v4_frozen import comparator_bytes_match
from src.models.dual_codec_search import MODELS

MANIFEST = REPO / "configs/v6_h265_frozen/manifest.json"


def frozen_manifest() -> dict:
    blob = subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}", "show",
         "HEAD:configs/v6_h265_frozen/manifest.json"], cwd=REPO)
    if MANIFEST.read_bytes().replace(b"\r\n", b"\n") != blob:
        raise ValueError("V6 freeze manifest differs from committed bytes")
    cfg = json.loads(blob)
    if (cfg["experiment"] != "v6_h265_frozen_before_new_holdout"
            or cfg["codec"] != "h265"
            or cfg["bootstrap_seed"] != 20261001
            or cfg["bootstrap_draws"] != 2000
            or digest(cfg["policy"]) != cfg["policy_digest"]):
        raise ValueError("invalid V6 freeze manifest")
    result_path = REPO / cfg["development_result_path"]
    if sha256(result_path) != cfg["development_result_sha256"]:
        raise ValueError("V6 DEV result bytes changed")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if (result["codec"] != "h265"
            or result["preregistration_commit"] != cfg["development_preregistration_commit"]
            or result["analysis_code_commit"] != cfg["development_analysis_commit"]
            or result["calibration"]["selected_policy"] != cfg["policy"]
            or result["dev"]["go_no_go_this_codec"] is not True
            or result["fitted_model_sha256"] != cfg["model_sha256"]):
        raise ValueError("V6 freeze differs from DEV selection")
    for key in ("policy", "risk"):
        rel = cfg[f"v2_{key}_path"]
        frozen_blob = subprocess.check_output(
            ["git", "-c", f"safe.directory={REPO.as_posix()}", "show",
             f"HEAD:{rel}"], cwd=REPO)
        if not comparator_bytes_match((REPO / rel).read_bytes(), frozen_blob,
                                      cfg[f"v2_{key}_sha256_bytes"],
                                      cfg[f"v2_{key}_sha256_git_blob"]):
            raise ValueError(f"V2 comparator {key} changed")
    if set(cfg["model_paths"]) != set(MODELS):
        raise ValueError("V6 model analyzer set changed")
    for model in MODELS:
        if set(cfg["model_paths"][model]) != {"harm", "gain"}:
            raise ValueError("V6 model event set changed")
        for event, rel in cfg["model_paths"][model].items():
            if sha256(REPO / rel) != cfg["model_sha256"][model][event]:
                raise ValueError(f"V6 {model}/{event} model bytes changed")
    return cfg


def load_frozen_v6() -> tuple[dict, dict]:
    cfg = frozen_manifest()
    models = {name: {event: joblib.load(REPO / rel)
                     for event, rel in cfg["model_paths"][name].items()}
              for name in MODELS}
    for name in MODELS:
        for event in ("harm", "gain"):
            model = models[name][event]
            if isinstance(model, dict):
                if set(model) != {"constant"} or model["constant"] not in (0.0, 1.0):
                    raise ValueError("invalid V6 constant model")
            elif model.n_features_in_ != 82:
                raise ValueError("V6 event model feature width changed")
    return cfg["policy"], models
