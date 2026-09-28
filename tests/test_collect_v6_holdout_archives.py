"""Reject incomplete or unsafe distributed preflight archives."""
import io
import tarfile

import pytest

from ops.collect_v6_holdout_archives import collect, safe_members


def test_collector_requires_four_shards_before_reading_video(tmp_path):
    with pytest.raises(ValueError, match="four shards"):
        collect([], tmp_path / "out", "a" * 40)


def test_tar_member_filter_allows_only_known_layout(tmp_path):
    valid = tmp_path / "valid.tar"
    with tarfile.open(valid, "w") as archive:
        directory = tarfile.TarInfo("videos/")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        data = b"{}"
        member = tarfile.TarInfo("shard_manifest.json")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    with tarfile.open(valid) as archive:
        assert set(safe_members(archive)) == {"shard_manifest.json"}

    invalid = tmp_path / "invalid.tar"
    with tarfile.open(invalid, "w") as archive:
        member = tarfile.TarInfo("../escape.json")
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))
    with tarfile.open(invalid) as archive, pytest.raises(ValueError, match="unsafe"):
        safe_members(archive)
