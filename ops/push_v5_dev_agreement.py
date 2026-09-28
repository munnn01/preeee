#!/usr/bin/env python
"""Upload a private V5 DEV cache dataset or push its commit-pinned Kaggle notebook."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from ops.push_dual_codec_search import require_inactive
from ops.push_rcts_pilot import account_environment, kaggle_command, notebook

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "kaggle/v5_dev_agreement_cell.sh"


def payload(commit: str, account: str, slug: str, dataset: str) -> tuple[dict, dict]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("full lowercase V5 code commit required")
    if not re.fullmatch(r"[a-z0-9]+", account):
        raise ValueError("invalid Kaggle account")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError("invalid Kaggle notebook slug")
    if not re.fullmatch(r"[a-z0-9]+/[a-z0-9][a-z0-9-]*", dataset):
        raise ValueError("invalid Kaggle dataset ID")
    owner, dataset_slug = dataset.split("/")
    if owner != account:
        raise ValueError("private DEV dataset must be owned by notebook account")
    shell = (TEMPLATE.read_text(encoding="utf-8")
             .replace("__REF__", commit)
             .replace("__DATASET_OWNER__", owner)
             .replace("__DATASET_SLUG__", dataset_slug))
    if not shell.startswith("%%bash\n") or re.search(r"__[A-Z_]+__", shell):
        raise ValueError("unsubstituted V5 notebook template")
    book = notebook(shell.removeprefix("%%bash\n"), "dev")
    book["cells"][0]["id"] = "v5-primary-agreement-dev-only"
    metadata = {"id": f"{account}/{slug}", "title": slug,
                "code_file": "notebook.ipynb", "language": "python",
                "kernel_type": "notebook", "is_private": True,
                "enable_gpu": False, "enable_internet": True,
                "dataset_sources": [dataset], "kernel_sources": [],
                "competition_sources": [], "model_sources": []}
    return book, metadata


def invoke(command: list[str], environment: dict) -> None:
    result = subprocess.run(command, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=environment,
                            check=False)
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output.encode("ascii", "backslashreplace").decode("ascii"), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dataset", "notebook"))
    parser.add_argument("--account", required=True)
    parser.add_argument("--path", type=Path, help="new packaged private dataset directory")
    parser.add_argument("--commit", help="pinned full code commit for notebook")
    parser.add_argument("--slug", help="new notebook slug")
    parser.add_argument("--dataset", help="private dataset ID")
    parser.add_argument("--pool", type=Path, default=Path("D:/STUDY/LAB/pool.json"))
    parser.add_argument("--write-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9]+", args.account):
        raise ValueError("invalid Kaggle account")
    if args.mode == "dataset":
        if args.path is None:
            raise ValueError("--path is required for dataset upload")
        package = args.path.resolve()
        info = json.loads((package / "dataset-metadata.json").read_text(encoding="utf-8"))
        if not info["id"].startswith(args.account + "/"):
            raise ValueError("dataset owner differs from authenticated account")
        if args.write_only:
            print(f"[V5 dataset] ready {info['id']}")
            return
        environment = account_environment(args.pool, args.account)
        environment["PYTHONIOENCODING"] = "utf-8"
        invoke(kaggle_command() + ["datasets", "create", "-p", str(package)], environment)
        return
    if args.commit is None or args.slug is None or args.dataset is None:
        raise ValueError("--commit, --slug and --dataset are required for notebook")
    book, meta = payload(args.commit, args.account, args.slug, args.dataset)
    target = REPO / "ops/_push" / args.account / args.slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "notebook.ipynb").write_text(json.dumps(book), encoding="utf-8")
    (target / "kernel-metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"[V5 DEV] generated {meta['id']} commit={args.commit}", flush=True)
    if args.write_only:
        return
    environment = account_environment(args.pool, args.account)
    environment["PYTHONIOENCODING"] = "utf-8"
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
