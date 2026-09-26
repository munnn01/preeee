"""Packaging rejects any shortcut that omits trial codec calls or memory."""

import hashlib
import json

import pytest

from ops import package_paper_runtime_full as package


def test_runtime_result_requires_all_five_qps_and_thirty_calls(tmp_path,
                                                                 monkeypatch):
    ids = [f"class/{number:011d}.mp4" for number in range(20)]
    sample_ids = tmp_path / "sample_ids.json"
    sample_ids.write_text(json.dumps(ids), encoding="utf-8")
    source_files = tmp_path / "source_files.json"
    source_files.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(package, "SAMPLE_IDS", sample_ids)
    monkeypatch.setattr(package, "SOURCE_FILES", source_files)
    sample_sha = hashlib.sha256(sample_ids.read_bytes()).hexdigest()
    fingerprint = hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()
    index_sha = "a" * 64
    commit = "b" * 40
    rows = [{"sequence_id": key, "identity_codec_calls": 5,
             "full_codec_calls": 30,
             "qps": [{"qp": qp} for qp in package.QPS],
             "arm_order": ["identity", "full"],
             "identity_only_s": 1.0, "full_selector_s": 2.0,
             "identity_peak_process_tree_rss_bytes": 100,
             "full_peak_process_tree_rss_bytes": 200}
            for key in ids]
    report = {"manifest": {"experiment": "dual_v2_full_runtime",
                           "codec": "h264", "split": "val", "clips": 20,
                           "sample_ids": ids, "sample_ids_sha256": sample_sha,
                           "sample_fingerprint": fingerprint,
                           "index_sha256": index_sha, "code_commit": commit,
                           "qps": list(package.QPS),
                           "candidates": list(package.CANDIDATES)},
              "summary": {"n": 20, "identity_codec_calls_per_clip": 5,
                          "full_codec_calls_per_clip": 30},
              "records": rows}
    path = tmp_path / "runtime_result.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    path.with_name("runtime_result.sha256").write_text(
        package.sha256(path) + "  runtime_result.json\n", encoding="utf-8")
    assert package.validate_result(path, "h264", index_sha,
                                   {"sample_fingerprint": fingerprint},
                                   commit)["summary"]["n"] == 20
    rows[0]["full_codec_calls"] = 5
    path.write_text(json.dumps(report), encoding="utf-8")
    path.with_name("runtime_result.sha256").write_text(
        package.sha256(path) + "  runtime_result.json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="full timing/memory"):
        package.validate_result(path, "h264", index_sha,
                                {"sample_fingerprint": fingerprint}, commit)
