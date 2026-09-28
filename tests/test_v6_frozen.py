"""Frozen H.265 V6 policy must resolve to the committed DEV model bytes."""
from ops.v6_frozen import MANIFEST, frozen_manifest, load_frozen_v6


def test_v6_freeze_matches_dev_result_and_four_models():
    assert MANIFEST.as_posix().endswith("configs/v6_h265_frozen/manifest.json")
    manifest = frozen_manifest()
    policy, models = load_frozen_v6()
    assert manifest["codec"] == "h265"
    assert policy == manifest["policy"]
    assert set(models) == {"r2plus1d_18", "r3d_18"}
    assert all(set(events) == {"harm", "gain"} for events in models.values())
