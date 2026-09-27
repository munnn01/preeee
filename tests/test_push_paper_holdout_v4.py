"""Private V4 notebooks must pin the protocol/index commit and owned dataset."""
from __future__ import annotations

import pytest

from ops.push_paper_holdout_v4 import payload


def test_v4_notebook_pins_commit_codec_shard_and_private_dataset():
    commit = "a" * 40
    book, meta = payload(commit, "shungg05", "v4-h264-shard0",
                         "shungg05/v4-new-holdout", "h264", 0)
    script = book["cells"][0]["source"]
    script = "".join(script) if isinstance(script, list) else script
    assert commit in script
    assert 'CODEC="h264"' in script
    assert 'SHARD="0"' in script
    assert "ops.paper_holdout_v4 primary" in script
    assert "ops.paper_holdout_v4 mc3" in script
    assert meta["is_private"] is True
    assert meta["dataset_sources"] == ["shungg05/v4-new-holdout"]


def test_v4_notebook_rejects_foreign_private_dataset():
    with pytest.raises(ValueError, match="owned"):
        payload("a" * 40, "shungg05", "v4-h264-shard0",
                "another/v4-new-holdout", "h264", 0)
