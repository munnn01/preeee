import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ops import v10_spatial_gate as gate
from ops.push_v10_spatial_gate import payload
from ops.v10_spatial_policy import choose, policy_grid, spatial_proxy
from src.models.codec_search import CANDIDATES, make_candidates


def policy(**changes):
    return {"complexity_quantile": .75, "complexity_threshold": .2, "tau": .05,
            "minimum_saving": .1, "spatial_weight": 1.0, **changes}


def observations():
    return {name: {"bpp": 1.0 if name == "identity128" else .8, "spatial_error": .2}
            for name in CANDIDATES}


def test_proxy_is_finite_identity_zero_and_sensitive_to_lost_edges():
    y, x = np.indices((128, 128))
    image = np.repeat((((x + y) % 2) * 255).astype(np.uint8)[..., None], 3, axis=2)
    clip = np.repeat(image[None], 16, axis=0)
    original = spatial_proxy(clip, clip)
    changed = spatial_proxy(clip, make_candidates(clip)["area112"])
    assert original["spatial_error"] == 0
    assert original["complexity"] > 0
    assert 0 < changed["spatial_error"] <= 2
    flat = np.zeros_like(clip)
    assert spatial_proxy(flat, flat) == {"complexity": 0.0, "spatial_error": 0.0}
    with pytest.raises(ValueError):
        spatial_proxy(clip.astype(np.float32), clip)


def test_grid_and_numeric_cal_threshold_are_deterministic():
    grid = policy_grid([.1, .2, .3, .4])
    assert len(grid) == 81
    assert grid == policy_grid([.4, .2, .1, .3])
    assert grid[0]["complexity_threshold"] == pytest.approx(.25)
    with pytest.raises(ValueError):
        policy_grid([float("nan")])


@pytest.mark.parametrize("qp", [30, 35])
def test_high_complexity_low_qp_cannot_be_overridden_by_huge_saving(qp):
    obs = observations()
    obs["area112"]["bpp"] = .01
    assert choose(qp, .2, obs, "area96", "area112", policy()) == ("identity128", "high_complexity_low_qp")


def test_high_qp_still_checks_spatial_loss_and_zero_source_not_high_complexity():
    obs = observations()
    obs["area112"]["spatial_error"] = .8
    assert choose(40, 1, obs, "area112", "area112", policy())[0] == "identity128"
    assert choose(30, 0, observations(), "area112", "area112", policy(complexity_threshold=0))[0] == "area112"


def test_low_qp_requires_rate_saving_over_spatial_tolerance():
    obs = observations()
    obs["area112"].update(bpp=.96, spatial_error=.22)
    assert choose(35, .1, obs, "area112", "area112", policy())[0] == "identity128"
    assert choose(40, .1, obs, "area112", "area112", policy())[0] == "area112"


def test_conservative_v6_switch_bound_and_tie_keep_base():
    obs = observations()
    assert choose(40, .1, obs, "area96", "area112", policy()) == ("area96", "v2_retained")
    obs["area112"]["bpp"] = .7
    assert choose(40, .1, obs, "area96", "area112", policy()) == ("area112", "v6_admitted")
    obs["area112"]["spatial_error"] = .28  # within high-QP identity budget, outside V2->V6 budget
    assert choose(40, .1, obs, "area96", "area112", policy())[0] == "area96"


@pytest.mark.parametrize("field", ["label", "correct", "mc3_18", "logits"])
def test_selector_rejects_task_information(field):
    obs = observations()
    obs["area112"][field] = 1
    with pytest.raises(ValueError):
        choose(40, .1, obs, "identity128", "area112", policy())


def engineering_report():
    return {m: {"metrics": {"bd_rate_top1_pct": -11 if m in gate.PRIMARY else -1,
                            "bd_accuracy_top1_pp": .1, "min_same_qp_top1_gap_pp": -1},
                "bootstrap": {k: {"valid_draws": 2000, "requested_draws": 2000, "ci95": [-2, 1]}
                              for k in ("bd_rate_top1_pct", "bd_accuracy_top1_pp")}}
            for m in gate.MODELS}


def test_engineering_gate_checks_all_models_and_strict_boundaries():
    report = engineering_report()
    assert gate.engineering_gate(report)["go_no_go"]
    for model, field, value in [("r3d_18", "bd_rate_top1_pct", -10),
                                 ("mc3_18", "bd_rate_top1_pct", 0),
                                 ("mc3_18", "bd_accuracy_top1_pp", 0),
                                 ("r2plus1d_18", "min_same_qp_top1_gap_pp", -1.01)]:
        bad = copy.deepcopy(report)
        bad[model]["metrics"][field] = value
        assert not gate.engineering_gate(bad)["go_no_go"]
    for value in ([0, 1.001], None, [2, 1], [float("nan"), 1]):
        bad = copy.deepcopy(report)
        bad["mc3_18"]["bootstrap"]["bd_rate_top1_pct"]["ci95"] = value
        assert not gate.engineering_gate(bad)["go_no_go"]
    report["r3d_18"]["bootstrap"]["bd_accuracy_top1_pp"]["valid_draws"] = 1899
    assert not gate.engineering_gate(report)["go_no_go"]


def test_draft_preregistration_stops_before_loading_sources(monkeypatch):
    monkeypatch.setattr(gate, "git", lambda *args: b"")
    monkeypatch.setattr(gate, "committed", lambda *args: b"\nPREREGISTRATION_LOCKED: false\n")
    with pytest.raises(ValueError, match="draft"):
        gate.protocol("a" * 40)


def synthetic_source(index=0):
    return {"sequence_id": f"abseiling/source{index}.mp4", "source_sha256": hashlib.sha256(str(index).encode()).hexdigest(),
            "measurements": [{"qp": q, "v2": "area112", "v6": "area96",
                              "bpp": {name: (size if name == "identity128" else int(.8 * size)) / 32768
                                      for name in CANDIDATES}}
                             for q, size in zip(gate.QPS, (16000, 10000, 6000, 4000, 3000), strict=True)]}


def synthetic_pixels(source, path=None, codec=None):
    clip = np.zeros((16, 128, 128, 3), dtype=np.uint8)
    measurements, decoded = [], {}
    for fixed in source["measurements"]:
        values = {}
        for name in CANDIDATES:
            decoded[(fixed["qp"], name)] = clip
            values[name] = {"bpp": fixed["bpp"][name], "spatial_error": .2, "encode_decode_s": .01,
                            "coded_bytes": round(fixed["bpp"][name] * 32768),
                            "decoded_sha256": gate.hash_bytes(clip.tobytes())}
        measurements.append({"qp": fixed["qp"], "candidates": values})
    return {"sequence_id": source["sequence_id"], "source_sha256": source["source_sha256"],
            "complexity": .1, "measurements": measurements}, decoded


def test_cal_records_reject_leaked_correctness_and_bad_rates():
    source = synthetic_source()
    row, _ = synthetic_pixels(source)
    gate.validate_record(row, source, "calibration", None)
    bad = copy.deepcopy(row)
    bad["label"] = 0
    with pytest.raises(ValueError):
        gate.validate_record(bad, source, "calibration", None)
    row["measurements"][0]["candidates"]["area112"]["bpp"] += .01
    with pytest.raises(ValueError):
        gate.validate_record(row, source, "calibration", None)


def test_no_dev_cache_read_without_committed_feasible_cal_result(monkeypatch, tmp_path):
    def reject(_):
        raise ValueError("CAL NO-GO")

    def forbidden(*args):
        pytest.fail("DEV cache must not be read before a valid freeze")

    monkeypatch.setattr(gate, "load_freeze", reject)
    monkeypatch.setattr(gate, "historical_stage", forbidden)
    with pytest.raises(ValueError, match="NO-GO"):
        gate.prepare_inputs(tmp_path, "dev", {}, {})


def test_cal_selection_uses_full_grid_then_freeze_rejects_tampering(tmp_path, monkeypatch):
    sources = [synthetic_source(i) for i in range(200)]
    pixels, cache = [], []
    for i, source in enumerate(sources):
        pixel, _ = synthetic_pixels(source)
        pixel["complexity"] = i / 200
        pixels.append(pixel)
        cache.append({"sequence_id": source["sequence_id"], "measurements": [
            {"qp": qp, "candidates": [{"name": name, "bpp": source["measurements"][j]["bpp"][name],
                                       **{field: i < cut for field in gate.FIELDS}} for name in CANDIDATES]}
            for j, (qp, cut) in enumerate(zip(gate.QPS, (160, 130, 100, 60, 20), strict=True))]})
    data = {"sources": sources}
    context = {"code_commit": "a" * 40}
    monkeypatch.setattr(gate, "REPO", tmp_path)
    monkeypatch.setattr(gate, "load_shards", lambda *args: (pixels, [], data, "inputhash"))
    monkeypatch.setattr(gate, "historical_stage", lambda *args: (cache, None, None))
    result = gate.calibrate([], tmp_path, {"source_fingerprints": {"calibration": "fp"}}, context)
    frozen = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert len(frozen["grid"]) == 81
    feasible = [row for row in frozen["grid"] if row["feasible"]]
    assert feasible, "synthetic identical-accuracy lower-rate curves must have feasible policies"
    assert frozen["selected_policy"] == min(feasible, key=gate.rank_key)["policy"]
    assert all(set(row["analyzers"]) == set(gate.PRIMARY) for row in frozen["grid"])
    frozen["grid"][0]["feasible"] = not frozen["grid"][0]["feasible"]
    monkeypatch.setattr(gate, "committed", lambda *args: json.dumps(frozen).encode())
    with pytest.raises(ValueError, match="feasibility"):
        gate.load_freeze(context)


def test_codec_bpp_mismatch_stops_proxy_collection(tmp_path, monkeypatch):
    source = synthetic_source()
    path = tmp_path / "source.mp4"
    path.write_bytes(b"0")
    monkeypatch.setattr(gate, "read_clip", lambda _: np.zeros((16, 128, 128, 3), dtype=np.uint8))

    class BadCodec:
        def _encode_decode_clip(self, candidate, qp):
            return candidate, .99

    with pytest.raises(ValueError, match="bpp mismatch"):
        gate.measure_pixels(source, path, BadCodec())


def test_four_shard_merge_orders_sources_and_rejects_duplication(tmp_path, monkeypatch):
    sources = [synthetic_source(i) for i in range(200)]
    data = {"sources": sources, "policy": None, "calibration_sha256": None}
    context = {"code_commit": "a" * 40, "test_context": 1}
    plan = {"source_fingerprints": {"calibration": "fp"}}
    monkeypatch.setattr(gate, "load_inputs", lambda *a: (data, "inputhash"))
    monkeypatch.setattr(gate, "git", lambda *a: b"")
    folders = []
    for shard in range(4):
        folder = tmp_path / str(shard)
        folder.mkdir()
        selected = sources[shard::4]
        rows = [synthetic_pixels(s)[0] for s in selected]
        raw = gate.rows_bytes(rows)
        for name in ("shard_records.jsonl", "proxy_records.jsonl"):
            (folder / name).write_bytes(raw)
        manifest = {"kind": "shard", "stage": "calibration", "shard": shard, "shards": 4,
                    "n": 50, "source_ids": [s["sequence_id"] for s in selected], "provenance": context,
                    "input_sha256": "inputhash", "source_fingerprint": "fp", "calibration_sha256": None,
                    "records_sha256": gate.hash_bytes(raw), "proxy_records_sha256": gate.hash_bytes(raw),
                    "trial_encode_decode_count": 1500, "weight_state_sha256": {}}
        (folder / "manifest.json").write_text(json.dumps(manifest))
        folders.append(folder)
    rows, manifests, _, _ = gate.load_shards(folders[::-1], "calibration", plan, context)
    assert [r["sequence_id"] for r in rows] == [s["sequence_id"] for s in sources]
    assert [m["shard"] for m in manifests] == list(range(4))
    with pytest.raises(ValueError, match="duplicate"):
        gate.load_shards([folders[0]] * 4, "calibration", plan, context)
    with (folders[0] / "shard_records.jsonl").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="hash"):
        gate.load_shards(folders, "calibration", plan, context)


def test_dev_writes_all_decisions_before_model_creation(tmp_path, monkeypatch):
    import torch
    import src.tasks.action_recognition as ar
    sources = [synthetic_source(i) for i in range(8)]
    paths = {}
    for i, source in enumerate(sources):
        path = tmp_path / f"{i}.mp4"
        path.write_bytes(str(i).encode())
        paths[source["sequence_id"]] = path
    data = {"sources": sources, "policy": policy(), "calibration_sha256": "frozen"}
    out = tmp_path / "output"
    monkeypatch.setattr(gate, "load_inputs", lambda *a: (data, "input"))
    monkeypatch.setattr(gate, "find_planned_videos", lambda *a: paths)
    monkeypatch.setattr(gate, "measure_pixels", synthetic_pixels)
    monkeypatch.setattr(gate, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(gate.subprocess, "check_output", lambda *a, **kw: "ffmpeg synthetic\n")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    called = []

    class FakeAnalyzer(torch.nn.Module):
        def __init__(self, name, clip_size):
            super().__init__()
            existing = (out / "proxy_records.jsonl").read_text().splitlines()
            assert len(existing) == 2  # every source in this shard, not only the first
            assert all('"choices"' in line and '"label"' not in line for line in existing)
            self.register_buffer("value", torch.zeros(1))
            called.append(name)

        def freeze(self):
            return self

        def predict(self, x):
            return torch.zeros((1, 400))

    monkeypatch.setattr(ar, "ActionRecognitionAnalyzer", FakeAnalyzer)
    manifest = gate.run_shard(tmp_path, "dev", 0, out, {"source_fingerprints": {"dev": "fp"}}, {})
    assert called == list(gate.MODELS)
    assert manifest["trial_encode_decode_count"] == 60
    rows = [json.loads(x) for x in (out / "shard_records.jsonl").read_text().splitlines()]
    for row, source in zip(rows, sources[::4], strict=True):
        gate.validate_record(row, source, "dev", policy())
    rows[0]["measurements"][0]["choices"]["v10"] = "area96"
    with pytest.raises(ValueError, match="choice"):
        gate.validate_record(rows[0], sources[0], "dev", policy())


@pytest.mark.parametrize("stage", ["calibration", "dev"])
def test_kaggle_payload_four_private_pinned_shards(stage):
    for shard in range(4):
        book, metadata = payload("a" * 40, "b" * 40, "shungg05", f"v10-{stage}-{shard}", stage, shard)
        shell = "".join(book["cells"][0]["source"])
        assert 'REF="' + "a" * 40 + '"' in shell
        assert 'PREREG="' + "b" * 40 + '"' in shell
        assert f'SHARD="{shard}"' in shell
        assert metadata["is_private"] is True
        assert metadata["enable_gpu"] == (stage == "dev")
    with pytest.raises(ValueError):
        payload("a" * 40, "b" * 40, "shungg05", "v10-test", "holdout", 0)
