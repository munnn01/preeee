"""The holdout launcher cannot accidentally broaden the frozen experiment."""

import pytest

from ops.push_paper_holdout_confirm import payload


def test_holdout_notebook_is_private_and_commit_pinned():
    commit = "a" * 40
    book, metadata = payload(commit, "qktttttttttt", "holdout-h264-shard0",
                             "qktttttttttt/locked-k400-val", "h264", 0)
    source = book["cells"][0]["source"]
    if isinstance(source, list):
        source = "".join(source)
    assert metadata["is_private"] is True
    assert metadata["dataset_sources"] == ["qktttttttttt/locked-k400-val"]
    assert commit in source
    assert 'CODEC="h264"' in source
    assert 'SHARD="0"' in source
    assert '--codec "$CODEC" --shard "$SHARD"' in source
    assert "ops.paper_holdout_confirm primary" in source
    assert "ops.paper_holdout_confirm mc3" in source
    assert "--prereg-commit" in source


@pytest.mark.parametrize("dataset,codec,shard", [
    ("other/locked-k400-val", "h264", 0),
    ("qktttttttttt/locked-k400-val", "mpeg4", 0),
    ("qktttttttttt/locked-k400-val", "h265", 2),
])
def test_holdout_notebook_rejects_mismatched_inputs(dataset, codec, shard):
    with pytest.raises(ValueError):
        payload("a" * 40, "qktttttttttt", "holdout-h264-shard0",
                dataset, codec, shard)
