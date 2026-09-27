"""The committed V4 model bytes must reproduce the development freeze."""
from __future__ import annotations

import numpy as np
import pytest

from ops.v4_frozen import frozen_manifest, load_frozen_v4


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
