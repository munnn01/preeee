import pytest

from ops.push_v6_dev_residual import payload


def test_private_cpu_notebook_uses_pinned_dev_runner_only():
    commit = "a" * 40
    book, meta = payload(commit, "shungg05", "v6-dev-test")
    source = "".join(book["cells"][0]["source"])
    assert meta["is_private"] is True
    assert meta["enable_gpu"] is False
    assert meta["dataset_sources"] == ["shungg05/v5-dev-cache-20260928"]
    assert f'REF="{commit}"' in source
    assert "python -m ops.v6_dev_residual" in source
    assert "Kaggle-extracted cache found" in source
    assert "ops.paper_holdout_v4" not in source
    assert "ops.paper_heldout_mc3" not in source


def test_other_accounts_and_datasets_are_rejected():
    with pytest.raises(ValueError, match="locked private DEV cache"):
        payload("a" * 40, "dieulinhh", "v6-dev-test")
    with pytest.raises(ValueError, match="locked private DEV cache"):
        payload("a" * 40, "shungg05", "v6-dev-test", "shungg05/other-data")
