import pytest

from ops import push_v5_dev_agreement
from ops.push_v5_dev_agreement import payload


def test_private_cpu_notebook_is_pinned_to_dev_only_runner():
    commit = "a" * 40
    book, meta = payload(commit, "shungg05", "v5-dev-test",
                         "shungg05/v5-dev-cache-20260928")
    source = "".join(book["cells"][0]["source"])
    assert meta["is_private"] is True
    assert meta["enable_gpu"] is False
    assert meta["dataset_sources"] == ["shungg05/v5-dev-cache-20260928"]
    assert f'REF="{commit}"' in source
    assert "python -m ops.v5_dev_agreement" in source
    assert "Kaggle-extracted cache found" in source
    assert "ops.paper_holdout_v4" not in source
    assert "ops.paper_heldout_mc3" not in source


def test_private_dataset_must_belong_to_notebook_account():
    with pytest.raises(ValueError, match="owned"):
        payload("a" * 40, "shungg05", "v5-dev-test",
                "dieulinhh/v5-dev-cache-20260928")


def test_upload_progress_is_safe_for_windows_console(monkeypatch, capsys):
    class Response:
        returncode = 0
        stdout = "uploaded ▍"
        stderr = ""

    monkeypatch.setattr(push_v5_dev_agreement.subprocess, "run",
                        lambda *args, **kwargs: Response())
    push_v5_dev_agreement.invoke(["kaggle"], {})
    assert "uploaded \\u258d" in capsys.readouterr().out
