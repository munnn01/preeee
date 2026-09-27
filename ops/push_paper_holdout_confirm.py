#!/usr/bin/env python
"""Generate a private commit-pinned holdout notebook without evaluating it."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from ops.push_dual_codec_search import require_inactive
from ops.push_rcts_pilot import account_environment, kaggle_command, notebook

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "kaggle/paper_holdout_confirm_cell.sh"


def payload(commit: str, account: str, slug: str, dataset: str,
            codec: str, shard: int) -> tuple[dict, dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("full lowercase preregistration commit SHA required")
    if not re.fullmatch(r"[a-z0-9]+", account):
        raise ValueError("invalid Kaggle account")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError("invalid Kaggle notebook slug")
    if not re.fullmatch(r"[a-z0-9]+/[a-z0-9][a-z0-9-]*", dataset):
        raise ValueError("invalid Kaggle dataset ID")
    if dataset.split("/")[0] != account:
        raise ValueError("private dataset must be owned by notebook account")
    if codec not in {"h264", "h265"} or shard not in {0, 1}:
        raise ValueError("codec/shard outside locked design")
    owner, dataset_slug = dataset.split("/")
    shell = (TEMPLATE.read_text(encoding="utf-8")
             .replace("__REF__", commit)
             .replace("__CODEC__", codec)
             .replace("__SHARD__", str(shard))
             .replace("__DATASET_OWNER__", owner)
             .replace("__DATASET_SLUG__", dataset_slug))
    if not shell.startswith("%%bash\n") or re.search(r"__[A-Z_]+__", shell):
        raise ValueError("unsubstituted holdout notebook template")
    book = notebook(shell.removeprefix("%%bash\n"), "holdout")
    book["cells"][0]["id"] = "paper-source-disjoint-holdout"
    metadata = {"id": f"{account}/{slug}", "title": slug,
                "code_file": "notebook.ipynb", "language": "python",
                "kernel_type": "notebook", "is_private": True,
                "enable_gpu": True, "enable_internet": True,
                "dataset_sources": [dataset], "kernel_sources": [],
                "competition_sources": [], "model_sources": []}
    return book, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--codec", choices=("h264", "h265"), required=True)
    parser.add_argument("--shard", type=int, choices=(0, 1), required=True)
    parser.add_argument("--pool", type=Path, default=Path("D:/STUDY/LAB/pool.json"))
    parser.add_argument("--write-only", action="store_true")
    args = parser.parse_args()
    book, meta = payload(args.commit, args.account, args.slug,
                         args.dataset, args.codec, args.shard)
    target = REPO / "ops/_push" / args.account / args.slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "notebook.ipynb").write_text(json.dumps(book), encoding="utf-8")
    (target / "kernel-metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"[holdout] generated {meta['id']} commit={args.commit}", flush=True)
    if args.write_only:
        return
    environment = account_environment(args.pool, args.account)
    environment["PYTHONIOENCODING"] = "utf-8"
    require_inactive(meta["id"], environment)
    result = subprocess.run(kaggle_command() + ["kernels", "push", "-p", str(target)],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=environment, check=False)
    output = (result.stdout + result.stderr).strip()
    print(output, flush=True)
    if result.returncode or "successfully pushed" not in output.lower():
        raise SystemExit(result.returncode or 1)


if __name__ == "__main__":
    main()
