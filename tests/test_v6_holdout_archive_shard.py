"""The distributed preflight only touches committed source/video metadata."""
import pytest

from ops.push_v6_holdout_archive import payload
from ops.v6_holdout_archive_shard import locked_inputs, run


def test_committed_candidate_lock_excludes_prior_holdouts():
    plan, ids, urls = locked_inputs()
    assert plan["status"] == "metadata_only"
    assert len(ids) == 2000
    assert len(urls) == 20


def test_archive_ranges_are_bounded_before_streaming(tmp_path):
    with pytest.raises(ValueError, match="0..20"):
        run(20, 21, tmp_path / "never-created")
    with pytest.raises(ValueError, match="0..20"):
        run(5, 5, tmp_path / "never-created")


def test_private_cpu_notebook_is_pinned_and_scoped():
    commit = "a" * 40
    book, meta = payload(commit, "shungg05", "v6-preflight-part0", 0, 5)
    source = "".join(book["cells"][0]["source"])
    assert commit in source
    assert 'START="0"' in source and 'STOP="5"' in source
    assert '--start "$START" --stop "$STOP"' in source
    assert meta["is_private"] and not meta["enable_gpu"]
    assert not meta["dataset_sources"]
    with pytest.raises(ValueError):
        payload(commit, "shungg05", "bad", 5, 21)
