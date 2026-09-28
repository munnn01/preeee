"""Only a private, commit-pinned H.265 Kaggle confirmation may launch."""
import pytest

from ops.push_paper_holdout_v6 import payload


def test_v6_gpu_payload_requires_h265_and_account_owned_private_dataset():
    commit = "b" * 40
    book, meta = payload(commit, "shungg05", "v6-h265-confirm-s0",
                         "shungg05/v6-holdout-locked", "h265", 0)
    source = "".join(book["cells"][0]["source"])
    assert commit in source and "ops.paper_holdout_v6 primary" in source
    assert "ops.paper_holdout_v6 mc3" in source
    assert meta["is_private"] and meta["enable_gpu"]
    assert meta["dataset_sources"] == ["shungg05/v6-holdout-locked"]
    with pytest.raises(ValueError):
        payload(commit, "shungg05", "bad", "shungg05/v6-holdout-locked", "h264", 0)
    with pytest.raises(ValueError):
        payload(commit, "shungg05", "bad", "dieulinhh/v6-holdout-locked", "h265", 0)
