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
