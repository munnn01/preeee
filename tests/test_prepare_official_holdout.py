"""ID-only holdout selection and source-inventory checks."""

import csv
import json
import hashlib

import pytest

from ops import prepare_official_holdout as holdout
from ops.prepare_official_holdout import (archive_urls, id_fingerprint,
                                          load_exclusion, ranked_ids)


def test_ranked_ids_ignore_labels_and_exclude_entire_sources(tmp_path):
    annotation = tmp_path / "val.csv"
    with annotation.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("label", "youtube_id",
                                                    "time_start", "time_end"))
        writer.writeheader()
        for number, key in enumerate(("aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc")):
            writer.writerow({"label": f"secret-{number}", "youtube_id": key,
                             "time_start": 0, "time_end": 10})
    before, audit = ranked_ids(annotation, {"bbbbbbbbbbb"})
    text = annotation.read_text(encoding="utf-8")
    annotation.write_text(text.replace("secret-", "changed-"), encoding="utf-8")
    after, _ = ranked_ids(annotation, {"bbbbbbbbbbb"})
    assert before == after
    assert set(before) == {"aaaaaaaaaaa", "ccccccccccc"}
    assert audit["excluded_source_overlap"] == 1


def test_inventory_fingerprint_must_cover_exact_ids(tmp_path):
    inventory = tmp_path / "inventory.json"
    ids = ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    inventory.write_text(json.dumps({"source_ids": ids, "source_count": 2,
                                     "source_fingerprint": id_fingerprint(ids)}),
                         encoding="utf-8")
    assert load_exclusion(inventory) == set(ids)
    inventory.write_text(json.dumps({"source_ids": ids, "source_count": 2,
                                     "source_fingerprint": "wrong"}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid legacy"):
        load_exclusion(inventory)


def test_archive_list_rejects_unexpected_source(tmp_path):
    path = tmp_path / "paths.txt"
    path.write_text("https://example.org/part_0.tar.gz\n", encoding="utf-8")
    with pytest.raises(ValueError, match="archive list"):
        archive_urls(path)


def test_archive_part_resume_verifies_retained_bytes(tmp_path, monkeypatch):
    (tmp_path / "parts").mkdir()
    calls = []

    def fake_stream(url, candidate_ids, out_dir):
        calls.append(url)
        videos = out_dir / "videos"
        videos.mkdir()
        payload = b"video bytes"
        (videos / "aaaaaaaaaaa_000000_000010.mp4").write_bytes(payload)
        return {"url": url, "retained": [{"filename":
                "aaaaaaaaaaa_000000_000010.mp4", "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest()}]}

    monkeypatch.setattr(holdout, "stream_archive", fake_stream)
    url = "https://s3.amazonaws.com/kinetics/400/val/part_0.tar.gz"
    assert holdout.archive_part(0, url, {"aaaaaaaaaaa"}, tmp_path)[0] == 0
    assert holdout.archive_part(0, url, {"aaaaaaaaaaa"}, tmp_path)[0] == 0
    assert calls == [url]
    (tmp_path / "videos/aaaaaaaaaaa_000000_000010.mp4").write_bytes(b"changed")
    with pytest.raises(ValueError, match="missing or changed"):
        holdout.archive_part(0, url, {"aaaaaaaaaaa"}, tmp_path)


def test_archive_part_retries_transient_timeout_before_committing(tmp_path,
                                                                 monkeypatch):
    (tmp_path / "parts").mkdir()
    calls = []
    monkeypatch.setattr(holdout.time, "sleep", lambda seconds: None)

    def fake_stream(url, candidate_ids, out_dir):
        calls.append(url)
        if len(calls) == 1:
            raise TimeoutError("connection stalled")
        return {"url": url, "retained": [], "compressed_sha256": "verified"}

    monkeypatch.setattr(holdout, "stream_archive", fake_stream)
    url = "https://s3.amazonaws.com/kinetics/400/val/part_0.tar.gz"
    _, report = holdout.archive_part(0, url, set(), tmp_path)
    assert len(calls) == 2
    assert report["compressed_sha256"] == "verified"
    assert json.loads((tmp_path / "parts/part_00.json").read_text()) == report
