"""The runtime notebook is commit-pinned, private and includes both codecs."""

import pytest

from ops.push_paper_runtime_full import payload


def test_payload_runs_full_codec_benchmark_from_exact_commit():
    commit = "a" * 40
    book, metadata = payload(commit, "qktttttttttt", "paper-full-runtime")
    shell = "".join(book["cells"][0]["source"])
    assert shell.startswith("%%bash\n") and shell.count("%%bash") == 1
    assert f'REF="{commit}"' in shell
    assert "for codec in h264 h265" in shell
    assert "--clips 20" in shell
    assert "--qps" not in shell  # all five QPs are fixed by the runner
    assert metadata["is_private"] and metadata["enable_gpu"]
    assert metadata["dataset_sources"] == ["qktttttttttt/kineticscleaned"]


def test_payload_rejects_unpinned_commit():
    with pytest.raises(ValueError, match="full lowercase"):
        payload("main", "qktttttttttt", "paper-full-runtime")
