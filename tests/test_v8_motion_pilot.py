import numpy as np
import cv2
import pytest

from ops.v8_motion_pilot import motion_protect, validate_record


def test_static_clip_blurs_without_protecting_pixels():
    rng = np.random.default_rng(7)
    frame = rng.integers(0, 256, size=(128, 128, 3), dtype=np.uint8)
    clip = np.repeat(frame[None], 16, axis=0)
    transformed, fraction = motion_protect(clip)
    expected = cv2.GaussianBlur(frame, (0, 0), 1.5)
    assert fraction == 0.0
    np.testing.assert_array_equal(transformed[0], expected)
    assert transformed.shape == clip.shape
    assert transformed.dtype == np.uint8


def test_moving_square_is_protected_and_transform_is_deterministic():
    clip = np.zeros((16, 128, 128, 3), dtype=np.uint8)
    clip[1, 40:48, 40:48] = 255
    transformed, fraction = motion_protect(clip)
    second, second_fraction = motion_protect(clip)
    np.testing.assert_array_equal(transformed, second)
    assert fraction == second_fraction
    assert 0 < fraction < 1
    assert transformed[1, 40, 40, 0] >= 254
    assert transformed[1, 39, 39, 0] <= 5


def test_wrong_shape_and_bpp_are_rejected():
    with pytest.raises(ValueError, match="expected"):
        motion_protect(np.zeros((15, 128, 128, 3), dtype=np.uint8))
    record = {
        "sequence_id": "class/video.mp4", "source_sha256": "a" * 64,
        "label": 0, "protected_mask_fraction": 0.0,
        "measurements": [
            {"qp": qp, "arms": {
                arm: {
                    "name": arm, "coded_bytes": 100,
                    "bpp": 0.0, "analyzers": {
                        model: {"predicted_class_index": 0, "correct": True}
                        for model in ("r2plus1d_18", "r3d_18", "mc3_18")
                    },
                }
                for arm in ("identity128", "area112", "blur040_128", "motionprotect128")
            }}
            for qp in (30, 35, 40, 45, 50)
        ],
    }
    with pytest.raises(ValueError, match="invalid coded"):
        validate_record(record, "class/video.mp4", "a" * 64, 0)
