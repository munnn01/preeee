"""The committed V4 model bytes must reproduce the development freeze."""
from __future__ import annotations

import json
import subprocess

import numpy as np
import pytest

from ops.v4_frozen import (MANIFEST, comparator_bytes_match, frozen_manifest,
                           load_frozen_v4)
from ops.v3_dev_policy import REPO


def test_frozen_manifest_matches_dev_run():
    manifest = frozen_manifest()
    assert manifest["codecs"]["h264"]["dev_go_no_go"] is False
    assert manifest["codecs"]["h265"]["dev_go_no_go"] is True
    for codec in ("h264", "h265"):
        policy, models = load_frozen_v4(codec)
        assert policy == manifest["codecs"][codec]["policy"]
        for model in models.values():
            proba = model.predict_proba(np.zeros((1, 41)))
            assert proba.shape == (1, 2)
            assert np.isfinite(proba).all()


def test_unknown_codec_rejected():
    with pytest.raises(ValueError, match="unsupported codec"):
        load_frozen_v4("vp9")


def test_v2_comparator_accepts_only_recorded_newline_variants():
    import hashlib

    lf = b'{"threshold": 1}\n'
    crlf = b'{"threshold": 1}\r\n'
    lf_sha = hashlib.sha256(lf).hexdigest()
    crlf_sha = hashlib.sha256(crlf).hexdigest()
    assert comparator_bytes_match(lf, lf, crlf_sha, lf_sha)
    assert comparator_bytes_match(crlf, lf, crlf_sha, lf_sha)
    assert not comparator_bytes_match(b'{"threshold": 2}\n', lf, crlf_sha, lf_sha)
    assert not comparator_bytes_match(crlf, lf, crlf_sha, "0" * 64)


def test_real_v2_comparator_git_blobs_match_both_recorded_hashes():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for cfg in manifest["codecs"].values():
        for key in ("policy", "risk"):
            relative = cfg[f"v2_comparator_{key}_path"]
            blob = subprocess.check_output(
                ["git", "-c", f"safe.directory={REPO.as_posix()}",
                 "show", f"HEAD:{relative}"], cwd=REPO)
            win_sha = cfg[f"v2_comparator_{key}_sha256_bytes"]
            blob_sha = cfg[f"v2_comparator_{key}_sha256_git_blob"]
            assert comparator_bytes_match(blob, blob, win_sha, blob_sha)
            assert comparator_bytes_match((REPO / relative).read_bytes(), blob,
                                          win_sha, blob_sha)
