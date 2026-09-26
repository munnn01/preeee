#!/usr/bin/env python
"""Frozen V2-C confirmation on a committed, source-disjoint K400 holdout.

``primary`` records six candidates with the two development analyzers; ``mc3``
scores identity and the already selected stream independently. ``merge`` builds
whole-1000-video curves and bootstraps after both 500-video shards exist. No
per-shard inferential result is produced.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
from pathlib import Path

import torch
import torchvision

from ops.codec_search_ar import QPS
from ops.dual_codec_search import (bootstrap, collect, digest, metrics, prepare,
                                   selected_arrays, validate_row, write_json)
from ops.dual_codec_search_confirm_1000 import (ARTIFACTS, CONFIG, file_sha256,
                                                load_frozen)
from ops.lock_official_holdout import (REPO, SOURCES_REL, IDS_REL, committed_lock,
                                       git, sha256)
from ops.paper_heldout_mc3 import evaluate_clip, summarize as mc3_summarize
from ops.paper_validation import fixed_arrays
from ops.rcts_pilot import clip_id
from src.codecs.standard import StandardCodec, ffmpeg_available
from src.data.video_dataset import VideoClipDataset
from src.models.codec_search import CANDIDATES
from src.models.dual_codec_search import MODELS
from src.tasks.action_recognition import ActionRecognitionAnalyzer, kinetics_categories

BOOTSTRAP_SEED = 20260924
BOOTSTRAP_DRAWS = 2000
BASELINES = ("area96", "area112")


def ready_index(index_path: Path, prereg_commit: str) -> tuple[dict, VideoClipDataset]:
    """Refuse any model evaluation before the exact index and protocol commit."""
    if len(prereg_commit) != 40 or any(c not in "0123456789abcdef" for c in prereg_commit):
        raise ValueError("a full preregistration commit SHA is required")
    subprocess.run(["git", "-c", f"safe.directory={REPO.as_posix()}",
                    "merge-base", "--is-ancestor", prereg_commit, "HEAD"],
                   cwd=REPO, check=True)
    prereg = (REPO / "docs/PREREGISTRATION.md").read_bytes()
    split = (REPO / "docs/HOLDOUT_SPLIT.md").read_bytes()
    if (git("show", f"{prereg_commit}:docs/PREREGISTRATION.md") !=
            prereg.replace(b"\r\n", b"\n")
            or b"PREREGISTRATION_LOCKED: true" not in prereg
            or git("show", f"{prereg_commit}:docs/HOLDOUT_SPLIT.md") !=
            split.replace(b"\r\n", b"\n")
            or git("show", f"{prereg_commit}:configs/holdout_source_audit/index.json")
            != index_path.read_bytes()):
        raise ValueError("preregistration, split or index is not frozen in Git")
    for relative in ("ops/paper_holdout_confirm.py", "ops/dual_codec_search.py",
                     "ops/paper_heldout_mc3.py", "src/metrics/bd_rate.py"):
        if (git("show", f"{prereg_commit}:{relative}") !=
                (REPO / relative).read_bytes().replace(b"\r\n", b"\n")):
            raise ValueError(f"evaluation code differs from preregistration: {relative}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    meta = index["meta"]
    ids_path = REPO / IDS_REL
    sources_path = REPO / SOURCES_REL
    ids, sources = committed_lock(meta["locked_commit"], ids_path, sources_path)
    records = index.get("test", [])
    if (len(records) != 1000 or [row["source_id"] for row in records] != ids
            or meta["selected_source_fingerprint"] !=
            sources["selected_source_fingerprint"]
            or meta["selected_sources_sha256"] != sha256(sources_path)):
        raise ValueError("index is not the locked 1,000-source holdout")
    for row, source in zip(records, sources["selected"]):
        path = Path(row["path"])
        if (path.name != source["filename"] or not path.is_file()
                or path.stat().st_size != source["bytes"]
                or sha256(path) != source["video_sha256"]):
            raise ValueError(f"holdout video changed: {row['source_id']}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if (config["qps"] != list(QPS) or config["candidates"] != list(CANDIDATES)
            or config["models"] != list(MODELS)):
        raise ValueError("frozen codec design changed")
    dataset = VideoClipDataset(index_path, split="test", num_frames=config["frames"],
                               frame_size=config["frame_size"],
                               temporal_stride=config["temporal_stride"],
                               train=False, return_metadata=True)
    return config, dataset


def manifest_base(index_path: Path, prereg_commit: str,
                  dataset: VideoClipDataset, codec: str, shard: int) -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    risk, frozen, policy = load_frozen(codec, config)
    indices = [i for i in range(1000) if i % 2 == shard]
    return {"experiment": "v2c_source_disjoint_holdout", "codec": codec,
            "shard": shard, "shards": 2, "n": 500,
            "sample_ids": [clip_id(dataset.samples[i]) for i in indices],
            "source_ids": [dataset.samples[i]["source_id"] for i in indices],
            "source_fingerprint":
            json.loads(index_path.read_text(encoding="utf-8"))["meta"]
            ["selected_source_fingerprint"],
            "index_sha256": sha256(index_path),
            "preregistration_commit": prereg_commit,
            "preregistration_sha256": sha256(REPO / "docs/PREREGISTRATION.md"),
            "code_commit": git("rev-parse", "HEAD").decode().strip(),
            "config_sha256_lf": file_sha256(CONFIG),
            "risk_model_sha256_lf": file_sha256(
                ARTIFACTS / codec / "risk_model.json"),
            "frozen_policy_sha256_lf": file_sha256(
                ARTIFACTS / codec / "frozen_policy.json"),
            "risk_model_sha256_bytes": sha256(
                ARTIFACTS / codec / "risk_model.json"),
            "frozen_policy_sha256_bytes": sha256(
                ARTIFACTS / codec / "frozen_policy.json"),
            "risk_digest": digest(risk), "policy_digest": digest(frozen),
            "policy": policy, "qps": list(QPS),
            "candidates": list(CANDIDATES), "models": list(MODELS),
            "bootstrap_unit": "source video; all QPs, arms and analyzers paired",
            "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_draws": BOOTSTRAP_DRAWS,
            "inference_seed": 53,
            "versions": {"python": platform.python_version(),
                         "torch": torch.__version__,
                         "torchvision": torchvision.__version__}}


def put_manifest(out_dir: Path, manifest: dict) -> None:
    path = out_dir / "manifest.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("output directory belongs to another holdout run")
    write_json(path, manifest)


def write_records(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(json.dumps(row, allow_nan=False) + "\n"
                                 for row in records), encoding="utf-8")
    temporary.replace(path)


def primary(args) -> None:
    if not ffmpeg_available():
        raise ValueError("ffmpeg and ffprobe required")
    config, dataset = ready_index(args.index, args.prereg_commit)
    risk, frozen, policy = load_frozen(args.codec, config)
    manifest = {**manifest_base(args.index, args.prereg_commit,
                                dataset, args.codec, args.shard),
                "stage": "primary_six_candidate"}
    put_manifest(args.out_dir, manifest)
    indices = [i for i in range(1000) if i % 2 == args.shard]
    torch.manual_seed(53)
    torch.set_num_threads(2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    analyzers = {name: ActionRecognitionAnalyzer(name, clip_size=112).freeze().to(device)
                 for name in MODELS}
    codec = StandardCodec(args.codec, preset=config["preset"], strict_decode=True)
    rows = collect(dataset, indices, analyzers, codec, args.out_dir,
                   "holdout_primary", digest(manifest))
    write_records(args.out_dir / "shard_records.jsonl", rows)
    print(f"[holdout-primary] {args.codec} shard={args.shard} records={len(rows)}")


def load_shard(path: Path, expected_stage: str, codec: str, shard: int) -> tuple[dict, list[dict]]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    records = [json.loads(line) for line in
               (path / "shard_records.jsonl").read_text(encoding="utf-8").splitlines()]
    if (manifest["experiment"] != "v2c_source_disjoint_holdout"
            or manifest["stage"] != expected_stage or manifest["codec"] != codec
            or manifest["shard"] != shard or len(records) != 500
            or [row["sequence_id"] for row in records] != manifest["sample_ids"]):
        raise ValueError("incomplete or mismatched holdout shard")
    return manifest, records


def mc3(args) -> None:
    if not ffmpeg_available():
        raise ValueError("ffmpeg and ffprobe required")
    config, dataset = ready_index(args.index, args.prereg_commit)
    if kinetics_categories("mc3_18") != kinetics_categories("r3d_18"):
        raise ValueError("mc3 Kinetics labels differ")
    state, frozen, policy = load_frozen(args.codec, config)
    primary_manifest, primary_rows = load_shard(
        args.primary_dir, "primary_six_candidate", args.codec, args.shard)
    by_id = {row["sequence_id"]: row for row in primary_rows}
    manifest = {**manifest_base(args.index, args.prereg_commit,
                                dataset, args.codec, args.shard),
                "stage": "independent_mc3_selected_stream",
                "primary_records_sha256": sha256(args.primary_dir / "shard_records.jsonl")}
    for key in ("sample_ids", "source_ids", "index_sha256", "policy_digest",
                "preregistration_commit", "source_fingerprint"):
        if primary_manifest[key] != manifest[key]:
            raise ValueError(f"mc3 and primary provenance differ: {key}")
    put_manifest(args.out_dir, manifest)
    torch.manual_seed(53)
    torch.set_num_threads(2)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    analyzer = ActionRecognitionAnalyzer("mc3_18", clip_size=112).freeze().to(device)
    codec = StandardCodec(args.codec, preset=config["preset"], strict_decode=True)
    records = []
    for number, index in enumerate(i for i in range(1000) if i % 2 == args.shard):
        key = clip_id(dataset.samples[index])
        cache = by_id[key]
        validate_row(cache, key, args.codec, digest(primary_manifest))
        path = args.out_dir / "cache" / f"clip_{number:04d}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
        else:
            record = evaluate_clip(dataset, index, cache, state, policy, analyzer, codec)
            for measurement in record["measurements"]:
                for arm in ("anchor", "trial"):
                    if abs(measurement[arm]["bpp"] -
                           measurement[arm]["cached_bpp"]) > 1e-9:
                        raise ValueError("mc3 stream re-encode differs from primary cache")
            write_json(path, record)
        if record["sequence_id"] != key:
            raise ValueError("stale mc3 video cache")
        records.append(record)
        print(f"[holdout-mc3] {args.codec} shard={args.shard} {number + 1}/500",
              flush=True)
    write_records(args.out_dir / "shard_records.jsonl", records)


def merged_rows(paths: list[Path], stage: str, codec: str,
                expected: dict) -> tuple[list[dict], list[dict]]:
    if len(paths) != 2:
        raise ValueError("exactly two shard directories required")
    bundles = [load_shard(path, stage, codec, shard) for shard, path in enumerate(paths)]
    for shard, (manifest, _) in enumerate(bundles):
        for key in ("index_sha256", "preregistration_commit", "source_fingerprint",
                    "policy_digest", "config_sha256_lf", "bootstrap_seed",
                    "bootstrap_draws"):
            if manifest[key] != expected[key]:
                raise ValueError(f"shard provenance mismatch: {key}")
        if (manifest["sample_ids"] != expected["all_sample_ids"][shard::2]
                or manifest["source_ids"] != expected["all_source_ids"][shard::2]):
            raise ValueError("shard IDs differ from preregistered index")
    by_id = {row["sequence_id"]: row for _, records in bundles for row in records}
    ids = [key for manifest, _ in bundles for key in manifest["sample_ids"]]
    if len(by_id) != 1000 or len(set(ids)) != 1000:
        raise ValueError("merged holdout must contain 1,000 distinct videos")
    return [by_id[key] for key in expected["all_sample_ids"]], [m for m, _ in bundles]


def gate_this_codec(primary_points: dict) -> bool:
    """Original strict point-estimate gate on both development analyzers."""
    return all(
        primary_points[model]["metrics"]["bd_rate_top1_pct"] is not None
        and primary_points[model]["metrics"]["bd_rate_top1_pct"] < -15
        and primary_points[model]["metrics"]["bd_accuracy_top1_pp"] is not None
        and primary_points[model]["metrics"]["bd_accuracy_top1_pp"] > 0
        for model in MODELS)


def merge(args) -> None:
    config, dataset = ready_index(args.index, args.prereg_commit)
    state, frozen, policy = load_frozen(args.codec, config)
    expected = {**manifest_base(args.index, args.prereg_commit,
                                 dataset, args.codec, 0),
                "all_sample_ids": [clip_id(row) for row in dataset.samples],
                "all_source_ids": [row["source_id"] for row in dataset.samples]}
    primary_rows, primary_manifests = merged_rows(
        args.primary_dir, "primary_six_candidate", args.codec, expected)
    mc3_rows, mc3_manifests = merged_rows(
        args.mc3_dir, "independent_mc3_selected_stream", args.codec, expected)
    if [r["sequence_id"] for r in primary_rows] != [r["sequence_id"] for r in mc3_rows]:
        raise ValueError("primary and mc3 videos are not paired")
    prepared = prepare(primary_rows, state)
    identity, _ = selected_arrays(prepared, {"mode": "identity"})
    selected, choices = selected_arrays(prepared, policy)
    arms = {"V2-C": (selected, choices)}
    for name in BASELINES:
        arms[name] = fixed_arrays(primary_rows, name)
    comparisons = {}
    for name, (array, arm_choices) in arms.items():
        comparisons[f"{name}_vs_identity"] = {
            "analyzers": metrics(identity, array),
            "bootstrap": bootstrap(identity, array, BOOTSTRAP_DRAWS,
                                   BOOTSTRAP_SEED), "choices": arm_choices}
    for name in BASELINES:
        comparisons[f"V2-C_vs_{name}"] = {
            "analyzers": metrics(arms[name][0], selected),
            "bootstrap": bootstrap(arms[name][0], selected, BOOTSTRAP_DRAWS,
                                   BOOTSTRAP_SEED)}
    mc3_result = mc3_summarize(mc3_rows, BOOTSTRAP_DRAWS)
    primary_points = comparisons["V2-C_vs_identity"]["analyzers"]
    point_gate_this_codec = gate_this_codec(primary_points)
    report = {"experiment": "v2c_source_disjoint_holdout", "codec": args.codec,
              "n": 1000, "source_fingerprint": expected["source_fingerprint"],
              "index_sha256": expected["index_sha256"],
              "config_sha256_lf": expected["config_sha256_lf"],
              "preregistration_commit": args.prereg_commit,
              "analysis_code_commit": git("rev-parse", "HEAD").decode().strip(),
              "bootstrap_unit": expected["bootstrap_unit"],
              "bootstrap_seed": BOOTSTRAP_SEED,
              "bootstrap_draws": BOOTSTRAP_DRAWS,
              "policy": policy, "risk_digest": digest(state),
              "policy_digest": digest(frozen),
              "point_gate_this_codec": point_gate_this_codec,
              "primary_shard_manifests": primary_manifests,
              "mc3_shard_manifests": mc3_manifests,
              "raw_record_sha256": {
                  "primary": [sha256(path / "shard_records.jsonl")
                              for path in args.primary_dir],
                  "mc3": [sha256(path / "shard_records.jsonl")
                          for path in args.mc3_dir]},
              "comparisons": comparisons, "mc3_vs_identity": mc3_result}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, report)
    args.out.with_suffix(".sha256").write_text(
        f"{sha256(args.out)}  {args.out.name}\n", encoding="utf-8")
    print(f"[holdout-merged] {args.codec} 1000 paired source videos")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("primary", "mc3", "merge"):
        p = sub.add_parser(command)
        p.add_argument("--index", type=Path, required=True)
        p.add_argument("--prereg-commit", required=True)
        p.add_argument("--codec", choices=("h264", "h265"), required=True)
        if command == "merge":
            p.add_argument("--primary-dir", type=Path, action="append", required=True)
            p.add_argument("--mc3-dir", type=Path, action="append", required=True)
            p.add_argument("--out", type=Path, required=True)
        else:
            p.add_argument("--shard", type=int, choices=(0, 1), required=True)
            p.add_argument("--out-dir", type=Path, required=True)
            if command == "mc3":
                p.add_argument("--primary-dir", type=Path, required=True)
    args = parser.parse_args()
    {"primary": primary, "mc3": mc3, "merge": merge}[args.command](args)


if __name__ == "__main__":
    main()
