#!/usr/bin/env python
"""Push a private, commit-pinned V6 DEV notebook using the locked V5 cache."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from ops.push_dual_codec_search import require_inactive
from ops.push_rcts_pilot import account_environment, kaggle_command, notebook

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "kaggle/v6_dev_residual_cell.sh"
LOCKED_DATASET = "shungg05/v5-dev-cache-20260928"


def payload(commit: str, account: str, slug: str,
            dataset: str = LOCKED_DATASET) -> tuple[dict, dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("full lowercase V6 code commit required")
    if not re.fullmatch(r"[a-z0-9]+", account):
        raise ValueError("invalid Kaggle account")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError("invalid Kaggle notebook slug")
    if dataset != LOCKED_DATASET or not dataset.startswith(account + "/"):
        raise ValueError("V6 requires the locked private DEV cache on its owner account")
    owner, dataset_slug = dataset.split("/")
    shell = (TEMPLATE.read_text(encoding="utf-8")
             .replace("__REF__", commit)
             .replace("__DATASET_OWNER__", owner)
             .replace("__DATASET_SLUG__", dataset_slug))
    if not shell.startswith("%%bash\n") or re.search(r"__[A-Z_]+__", shell):
        raise ValueError("unsubstituted V6 notebook template")
    book = notebook(shell.removeprefix("%%bash\n"), "dev")
    book["cells"][0]["id"] = "v6-paired-residual-dev-only"
    metadata = {"id": f"{account}/{slug}", "title": slug,
                "code_file": "notebook.ipynb", "language": "python",
                "kernel_type": "notebook", "is_private": True,
                "enable_gpu": False, "enable_internet": True,
                "dataset_sources": [dataset], "kernel_sources": [],
                "competition_sources": [], "model_sources": []}
    return book, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="shungg05")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--pool", type=Path, default=Path("D:/STUDY/LAB/pool.json"))
    parser.add_argument("--write-only", action="store_true")
    args = parser.parse_args()
    book, meta = payload(args.commit, args.account, args.slug)
    target = REPO / "ops/_push" / args.account / args.slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "notebook.ipynb").write_text(json.dumps(book), encoding="utf-8")
    (target / "kernel-metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"[V6 DEV] generated {meta['id']} commit={args.commit}", flush=True)
    if args.write_only:
        return
    environment = account_environment(args.pool, args.account)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    require_inactive(meta["id"], environment)
    result = subprocess.run(kaggle_command() + ["kernels", "push", "-p", str(target)],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=environment, check=False)
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output.encode("ascii", "backslashreplace").decode("ascii"), flush=True)
    if result.returncode or "successfully pushed" not in output.lower():
        raise SystemExit(result.returncode or 1)


if __name__ == "__main__":
    main()
