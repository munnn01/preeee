#!/usr/bin/env python
"""Extract label-free V7 CAL/DEV pixel proxies from the original six streams."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np

from src.data.video_dataset import VideoClipDataset
from src.models.codec_search import CANDIDATES, make_candidates

REPO = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO / "configs/v7_dev_proxy_plan.json"
PLAN_SHA256 = "5b0a32d1d0a1759b50232f0c297ee35ee5cfe0cfdf00c53b587781baa5afebc2"
PREREG_COMMIT = "6c4a03d4e95d3f549adddf0a890704a334eb3a39"
STAGES = ("calibration", "dev")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_protocol() -> tuple[dict, str]:
    git = ["git", "-c", f"safe.directory={REPO.as_posix()}"]
    subprocess.run(git + ["merge-base", "--is-ancestor", PREREG_COMMIT, "HEAD"],
                   cwd=REPO, check=True, capture_output=True)
    for rel in ("docs/PREREGISTRATION_V7_TRANSFER.md",
                "configs/v7_dev_proxy_plan.json"):
        committed = subprocess.check_output(git + ["show", f"{PREREG_COMMIT}:{rel}"], cwd=REPO)
        if (REPO / rel).read_bytes().replace(b"\r\n", b"\n") != committed:
            raise ValueError(f"V7 preregistration input changed: {rel}")
    if sha256(PLAN_PATH) != PLAN_SHA256:
        raise ValueError("V7 source plan SHA-256 changed")
    for rel in ("ops/v7_pixel_proxy.py", "ops/v7_dev_transfer.py",
                "kaggle/v7_pixel_proxy_cell.sh"):
        subprocess.run(git + ["ls-files", "--error-unmatch", rel], cwd=REPO,
                       check=True, capture_output=True)
        subprocess.run(git + ["diff", "--quiet", "HEAD", "--", rel], cwd=REPO,
                       check=True, capture_output=True)
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if (plan.get("shards") != {"calibration": 0, "dev": 1}
            or {k: len(plan["stage_ids"][k]) for k in STAGES}
            != {"calibration": 200, "dev": 200}
            or len(set(plan["stage_ids"]["calibration"])
               | set(plan["stage_ids"]["dev"])) != 400):
        raise ValueError("V7 source plan structure changed")
    commit = subprocess.check_output(git + ["rev-parse", "HEAD"], cwd=REPO,
                                     text=True).strip()
    return plan, commit


def proxy_metrics(source: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    """Normalized edge and temporal errors using only pre-codec pixels."""
    if (source.shape != (16, 128, 128, 3) or source.dtype != np.uint8
            or candidate.ndim != 4 or candidate.shape[0] != 16
            or candidate.shape[-1] != 3 or candidate.dtype != np.uint8):
        raise ValueError("invalid V7 proxy clip")
    if candidate.shape[1:3] == (128, 128):
        resized = candidate
    else:
        resized = np.stack([cv2.resize(frame, (128, 128),
                                       interpolation=cv2.INTER_LINEAR)
                            for frame in candidate])
    clean_gray = np.stack([cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                           for frame in source]).astype(np.float32)
    trial_gray = np.stack([cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                           for frame in resized]).astype(np.float32)
    clean_edge = np.stack([cv2.Laplacian(frame, cv2.CV_32F, ksize=3,
                                         borderType=cv2.BORDER_DEFAULT)
                           for frame in clean_gray])
    trial_edge = np.stack([cv2.Laplacian(frame, cv2.CV_32F, ksize=3,
                                         borderType=cv2.BORDER_DEFAULT)
                           for frame in trial_gray])
    spatial = float(np.clip(np.abs(trial_edge - clean_edge).mean()
                            / max(float(np.abs(clean_edge).mean()), 1.0), 0.0, 2.0))
    clean_delta = np.diff(clean_gray, axis=0)
    trial_delta = np.diff(trial_gray, axis=0)
    temporal = float(np.clip(np.abs(trial_delta - clean_delta).mean()
                             / max(float(np.abs(clean_delta).mean()), 1.0), 0.0, 2.0))
    return {"spatial": spatial, "temporal": temporal,
            "proxy": max(spatial, temporal)}


def find_planned_videos(root: Path, ids: list[str]) -> dict[str, Path]:
    wanted = set(ids)
    matches: dict[str, Path] = {}
    for path in root.rglob("*.mp4"):
        key = "/".join(path.parts[-2:])
        if key not in wanted:
            continue
        if key in matches:
            raise ValueError(f"duplicate planned source ID: {key}")
        matches[key] = path
    if set(matches) != wanted:
        raise ValueError(f"{len(wanted - set(matches))} planned DEV sources missing")
    return matches


def extract_one(key: str, path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    ok, _ = cap.read()
    cap.release()
    if not ok:
        raise ValueError(f"undecodable planned DEV source: {key}")
    dataset = VideoClipDataset.__new__(VideoClipDataset)
    dataset.num_frames, dataset.frame_size = 16, 128
    dataset.temporal_stride, dataset.train = 2, False
    source = dataset._read_clip(str(path))
    variants = make_candidates(source)
    values = {name: proxy_metrics(source, variants[name]) for name in CANDIDATES}
    if any(values["identity128"][metric] != 0.0
           for metric in ("spatial", "temporal", "proxy")):
        raise ValueError("identity pixel proxy must be exactly zero")
    return {"sequence_id": key, "source_sha256": sha256(path),
            "proxy_by_candidate": values}


def run(root: Path, stage: str, out_dir: Path) -> dict:
    plan, commit = verify_protocol()
    if stage not in STAGES or out_dir.exists() or not root.is_dir():
        raise ValueError("stage, source root or fresh output directory invalid")
    ids = plan["stage_ids"][stage]
    paths = find_planned_videos(root, ids)
    out_dir.mkdir(parents=True)
    records_path = out_dir / "shard_records.jsonl"
    with records_path.open("w", encoding="utf-8", newline="\n") as stream:
        for number, key in enumerate(ids, 1):
            record = extract_one(key, paths[key])
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            print(f"[V7 pixel] {stage} {number}/{len(ids)}", flush=True)
    manifest = {"experiment": "v7_h265_dev_pixel_proxy", "stage": stage,
                "n": len(ids), "source_ids": ids,
                "source_fingerprint": plan["source_fingerprints"][stage],
                "plan_sha256": PLAN_SHA256, "preregistration_commit": PREREG_COMMIT,
                "code_commit": commit, "records_sha256": sha256(records_path),
                "opencv_version": cv2.__version__,
                "bootstrap_unit": "source video"}
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.source_root, args.stage, args.out_dir),
                     indent=2), flush=True)


if __name__ == "__main__":
    main()
