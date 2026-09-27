"""Packaging preserves the selected order and exact video bytes."""
from __future__ import annotations

import hashlib
import zipfile

import pytest

from ops.package_v4_holdout_dataset import zip_selected


def test_zip_selected_checks_hash_and_order(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    sources = []
    for name, content in (("b.mp4", b"bbb"), ("a.mp4", b"aaa")):
        (videos / name).write_bytes(content)
        sources.append({"filename": name, "bytes": len(content),
                        "video_sha256": hashlib.sha256(content).hexdigest()})
    count, total = zip_selected(sources, videos, tmp_path / "videos.zip")
    assert (count, total) == (2, 6)
    with zipfile.ZipFile(tmp_path / "videos.zip") as archive:
        assert archive.namelist() == ["videos/b.mp4", "videos/a.mp4"]
        assert archive.read("videos/b.mp4") == b"bbb"
    sources[0]["video_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="changed"):
        zip_selected(sources, videos, tmp_path / "bad.zip")
