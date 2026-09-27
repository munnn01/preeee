"""Load the exact CALIBRATION-selected V4 policy and model bytes.

This module has no data-selection or fitting path. Holdout runners call it only
after the manifest has been committed and the holdout index has been locked.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import joblib

from ops.v3_dev_policy import REPO, file_sha256
from ops.dual_codec_search import digest
from src.models.dual_codec_search import MODELS

MANIFEST = REPO / "configs/v4_frozen/manifest.json"


def comparator_bytes_match(working: bytes, git_blob: bytes,
                           working_sha: str, git_blob_sha: str) -> bool:
    """Accept only the two recorded Git/Windows newline encodings."""
    actual = hashlib.sha256(working).hexdigest()
    return (hashlib.sha256(git_blob).hexdigest() == git_blob_sha
            and actual in {working_sha, git_blob_sha}
            and working.replace(b"\r\n", b"\n") == git_blob)


def frozen_manifest(path: Path = MANIFEST) -> dict:
    if path.resolve() != MANIFEST.resolve():
        raise ValueError("V4 frozen manifest path changed")
    current = path.read_bytes().replace(b"\r\n", b"\n")
    committed = subprocess.check_output(
        ["git", "-c", f"safe.directory={REPO.as_posix()}",
         "show", "HEAD:configs/v4_frozen/manifest.json"], cwd=REPO)
    if current != committed:
        raise ValueError("V4 manifest is not the committed version")
    manifest = json.loads(current)
    if (manifest.get("experiment") !=
            "v4_correctness_selector_frozen_before_new_holdout"
            or manifest.get("bootstrap_draws") != 2000
            or manifest.get("bootstrap_seed") != 20260928
            or set(manifest.get("codecs", {})) != {"h264", "h265"}):
        raise ValueError("invalid V4 frozen manifest")
    if not any(manifest["codecs"][c]["dev_go_no_go"] for c in ("h264", "h265")):
        raise ValueError("V4 has no codec passing DEV go/no-go")
    for codec, cfg in manifest["codecs"].items():
        result_path = REPO / cfg["dev_result_path"]
        if file_sha256(result_path) != cfg["dev_result_sha256"]:
            raise ValueError(f"{codec} DEV result changed")
        dev = json.loads(result_path.read_text(encoding="utf-8"))
        if (dev["codec"] != codec
                or dev["preregistration_commit"] != manifest["preregistration_commit"]
                or dev["analysis_code_commit"] != manifest["analysis_code_commit"]
                or dev["selection"]["selected_policy"] != cfg["policy"]
                or dev["selection"]["promoted"] != cfg["calibration_promoted"]
                or dev["dev"]["go_no_go_this_codec"] != cfg["dev_go_no_go"]
                or dev["input_provenance"]["source_fingerprints"] !=
                   manifest["development_source_fingerprints"]
                or digest(cfg["policy"]) != cfg["policy_digest"]):
            raise ValueError(f"{codec} frozen policy differs from DEV selection")
        for key in ("policy", "risk"):
            path_key = f"v2_comparator_{key}_path"
            sha_key = f"v2_comparator_{key}_sha256_bytes"
            blob_sha_key = f"v2_comparator_{key}_sha256_git_blob"
            relative_path = cfg[path_key]
            blob = subprocess.check_output(
                ["git", "-c", f"safe.directory={REPO.as_posix()}",
                 "show", f"HEAD:{relative_path}"], cwd=REPO)
            if not comparator_bytes_match((REPO / relative_path).read_bytes(),
                                          blob, cfg[sha_key], cfg[blob_sha_key]):
                raise ValueError(f"{codec} V2 comparator {key} changed")
        if set(cfg["model_paths"]) != set(MODELS):
            raise ValueError(f"{codec} model names changed")
        for name in MODELS:
            path_model = REPO / cfg["model_paths"][name]
            if (file_sha256(path_model) != cfg["model_sha256"][name]
                    or dev["fitted_model_sha256"][name] != cfg["model_sha256"][name]):
                raise ValueError(f"{codec}/{name} model bytes changed")
    return manifest


def load_frozen_v4(codec: str) -> tuple[dict, dict]:
    manifest = frozen_manifest()
    if codec not in manifest["codecs"]:
        raise ValueError("unsupported codec")
    cfg = manifest["codecs"][codec]
    models = {name: joblib.load(REPO / cfg["model_paths"][name]) for name in MODELS}
    if any(model.n_features_in_ != 41 for model in models.values()):
        raise ValueError("V4 model feature width changed")
    return cfg["policy"], models
