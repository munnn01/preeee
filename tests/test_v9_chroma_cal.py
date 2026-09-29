import cv2
import numpy as np
import pytest

from ops.v9_chroma_cal import chroma_blend, validate_record


def test_gray_clip_is_exact_and_y_roundtrip_error_zero():
    rng = np.random.default_rng(12)
    gray = rng.integers(0, 256, size=(16, 96, 96), dtype=np.uint8)
    rgb = np.repeat(gray[..., None], 3, axis=-1)
    edited, y_error = chroma_blend(rgb)
    np.testing.assert_array_equal(edited, rgb)
    assert y_error == 0


def test_chroma_high_frequency_reduces_while_y_is_preserved():
    frame = np.zeros((96, 96, 3), dtype=np.uint8)
    frame[:, ::2] = (250, 30, 30)
    frame[:, 1::2] = (30, 30, 250)
    clip = np.repeat(frame[None], 16, axis=0)
    edited, y_error = chroma_blend(clip)
    original_ycc = cv2.cvtColor(frame, cv2.COLOR_RGB2YCrCb)
    edited_ycc = cv2.cvtColor(edited[0], cv2.COLOR_RGB2YCrCb)
    assert edited.shape == clip.shape
    assert edited.dtype == np.uint8
    assert y_error <= 1.0
    assert (edited_ycc[:, ::2, 1].astype(float)
            - edited_ycc[:, 1::2, 1].astype(float)).mean() < (
                original_ycc[:, ::2, 1].astype(float)
                - original_ycc[:, 1::2, 1].astype(float)).mean()


def test_bad_input_and_cached_bitrate_mismatch_rejected():
    with pytest.raises(ValueError, match="expected"):
        chroma_blend(np.zeros((15, 128, 128, 3), dtype=np.uint8))
    bpp = 8 * 100 / (16 * 128 * 128)
    choice = {"identity": "identity128", "v6": "area112",
              "cached_bpp": {"identity": bpp, "v6": bpp}}
    source = {"sequence_id": "class/video.mp4", "source_sha256": "a" * 64,
              "measurements": [{"qp": qp, **choice} for qp in (30, 35, 40, 45, 50)]}
    arm = lambda name: {
        "name": name, "coded_bytes": 100, "bpp": bpp,
        "analyzers": {model: {"predicted_class_index": 0, "correct": True}
                      for model in ("r2plus1d_18", "r3d_18", "mc3_18")},
    }
    record = {
        "sequence_id": source["sequence_id"], "source_sha256": source["source_sha256"],
        "label": 0,
        "measurements": [{"qp": qp, "y_roundtrip_mae": 0.0,
                          "arms": {"identity": arm("identity128"),
                                   "v6": arm("area112"), "v9": arm("v6_chroma050")}}
                         for qp in (30, 35, 40, 45, 50)],
    }
    validate_record(record, source, 0)
    record["measurements"][0]["arms"]["v6"]["coded_bytes"] += 1
    record["measurements"][0]["arms"]["v6"]["bpp"] = 8 * 101 / (16 * 128 * 128)
    with pytest.raises(ValueError, match="V2 cache bitrate"):
        validate_record(record, source, 0)
