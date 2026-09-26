"""ID-only holdout selection and source-inventory checks."""

import csv
import json

import pytest

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
