"""The label index cannot be built from an uncommitted or changed ID lock."""

import hashlib
import json

import pytest

from ops import lock_official_holdout as lock


def test_committed_lock_verifies_exact_bytes_and_source_fingerprint(tmp_path,
                                                                    monkeypatch):
    ids = [f"{number:011d}" for number in range(1000)]
    ids_path = tmp_path / "selected_ids.txt"
    sources_path = tmp_path / "selected_sources.json"
    ids_path.write_text("\n".join(ids) + "\n", encoding="utf-8")
    sources = {"selected_ids_sha256": hashlib.sha256(ids_path.read_bytes()).hexdigest(),
               "selected_source_fingerprint": lock.id_fingerprint(ids),
               "selected": [{"source_id": key} for key in ids]}
    sources_path.write_text(json.dumps(sources), encoding="utf-8")
    committed = {lock.IDS_REL: ids_path.read_bytes(),
                 lock.SOURCES_REL: sources_path.read_bytes()}
    monkeypatch.setattr(lock.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(lock, "git", lambda _cmd, spec: committed[spec.split(":", 1)[1]])
    assert lock.committed_lock("a" * 40, ids_path, sources_path)[0] == ids
    ids_path.write_text(ids_path.read_text(encoding="utf-8") + "extra\n",
                        encoding="utf-8")
    with pytest.raises(ValueError, match="differs from commit"):
        lock.committed_lock("a" * 40, ids_path, sources_path)


def test_index_refuses_to_read_labels_before_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "committed_lock", lambda *args:
                        (_ for _ in ()).throw(ValueError("uncommitted ID lock")))
    with pytest.raises(ValueError, match="uncommitted ID lock"):
        lock.build_index("a" * 40, tmp_path / "ids", tmp_path / "sources",
                         tmp_path / "missing_annotation.csv", tmp_path / "videos",
                         tmp_path / "index.json")
    assert not (tmp_path / "index.json").exists()


def test_index_joins_committed_id_to_canonical_kinetics_label(tmp_path, monkeypatch):
    source_id = "aaaaaaaaaaa"
    filename = source_id + "_000000_000010.mp4"
    videos = tmp_path / "videos"
    videos.mkdir()
    payload = b"fixed source bytes"
    (videos / filename).write_bytes(payload)
    annotation = tmp_path / "val.csv"
    annotation.write_text(
        "label,youtube_id,time_start,time_end\n"
        f"abseiling,{source_id},0,10\n", encoding="utf-8")
    sources_path = tmp_path / "selected_sources.json"
    sources_path.write_text("{}", encoding="utf-8")
    sources = {"annotation_sha256": lock.sha256(annotation),
               "source": "synthetic K400 validation", "selected_ids_sha256": "test",
               "selected_source_fingerprint": lock.id_fingerprint([source_id]),
               "selected": [{"source_id": source_id, "filename": filename,
                             "bytes": len(payload),
                             "video_sha256": hashlib.sha256(payload).hexdigest()}]}
    monkeypatch.setattr(lock, "committed_lock", lambda *args: ([source_id], sources))
    output = tmp_path / "index.json"
    lock.build_index("a" * 40, tmp_path / "ids", sources_path, annotation,
                     videos, output)
    index = json.loads(output.read_text(encoding="utf-8"))
    assert index["test"][0]["source_id"] == source_id
    assert index["test"][0]["label"] == 0
    assert index["meta"]["locked_commit"] == "a" * 40
