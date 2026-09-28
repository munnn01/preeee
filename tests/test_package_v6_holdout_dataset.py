"""The GPU input ZIP must preserve the committed video bytes and order."""
import hashlib
import zipfile

import pytest

from ops.package_v6_holdout_dataset import zip_selected


def test_zip_selected_checks_video_sha_and_member_order(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    rows = []
    for name, data in (("AAAAAAAAAAA_000001_000002.mp4", b"first"),
                       ("BBBBBBBBBBB_000001_000002.mp4", b"second")):
        (videos / name).write_bytes(data)
        rows.append({"filename": name, "bytes": len(data),
                     "video_sha256": hashlib.sha256(data).hexdigest()})
    output = tmp_path / "videos.zip"
    assert zip_selected(rows, videos, output) == (2, 11)
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["videos/" + row["filename"] for row in rows]
    (videos / rows[0]["filename"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="changed"):
        zip_selected(rows, videos, tmp_path / "bad.zip")
