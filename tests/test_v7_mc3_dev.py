from copy import deepcopy

import numpy as np
import pytest

from ops.codec_search_ar import QPS
from ops.push_v7_mc3_dev import payload
from ops.v7_mc3_dev import curve, summarize, validate_record


def test_record_validation_rejects_changed_stream_or_score():
    choices = [{"qp": qp, "identity": "identity128", "v6": "identity128",
                "v7": "identity128",
                "cached_bpp": {"identity": 0.1, "v6": 0.1, "v7": 0.1}}
               for qp in QPS]
    source = {"sequence_id": "abseiling/example.mp4", "source_sha256": "a" * 64,
              "measurements": choices}
    point = {"name": "identity128", "bpp": 0.1,
             "predicted_class_index": 3, "correct": True}
    record = {"sequence_id": source["sequence_id"],
              "source_sha256": source["source_sha256"], "label": 3,
              "measurements": [{"qp": qp, "identity": point, "v6": point,
                                "v7": point, "unique_streams": 1} for qp in QPS]}
    validate_record(record, source, 3)
    changed = deepcopy(record)
    changed["measurements"][0]["v7"] = {**point, "name": "area96"}
    with pytest.raises(ValueError):
        validate_record(changed, source, 3)
    changed = deepcopy(record)
    changed["measurements"][0]["v7"] = {**point, "correct": False}
    with pytest.raises(ValueError):
        validate_record(changed, source, 3)


def test_summary_uses_whole_source_paired_curves():
    records = []
    for source in range(20):
        measurements = []
        for q, qp in enumerate(QPS):
            correct = source < (18 - 4 * q)
            point = lambda rate: {"bpp": rate, "correct": correct}
            measurements.append({"qp": qp, "identity": point(0.25 - q * 0.04),
                                 "v6": point((0.25 - q * 0.04) * 0.95),
                                 "v7": point((0.25 - q * 0.04) * 0.90)})
        records.append({"measurements": measurements})
    draws = np.random.default_rng(20261004).integers(0, 20, (100, 20))
    report = summarize(records, "v6", "v7", draws)
    assert report["n"] == 20
    assert report["metrics"]["bd_rate_top1_pct"] < 0
    assert report["bootstrap"]["bd_rate_top1_pct"]["requested_draws"] == 100
    assert report["anchor_curve"]["30"]["n"] == 20
    assert curve(records, "identity")["50"]["top1"] == 0.1


def test_private_shard_payload_is_pinned_and_bounded():
    book, meta = payload("a" * 40, "shungg05", "v7-mc3-dev-s0", 0)
    shell = "".join(book["cells"][0]["source"])
    assert meta["is_private"] is True
    assert meta["enable_gpu"] is True
    assert "a" * 40 in shell
    assert 'SHARD="0"' in shell
    with pytest.raises(ValueError):
        payload("a" * 40, "shungg05", "v7-mc3-dev-s4", 4)
