"""Create/push a private V10 shard; draft protocols can generate payloads but cannot run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

from ops.push_dual_codec_search import require_inactive
from ops.push_rcts_pilot import account_environment, kaggle_command, notebook

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "kaggle/v10_spatial_gate_cell.sh"


def payload(commit: str, prereg: str, account: str, slug: str, stage: str, shard: int) -> tuple[dict, dict]:
    if any(not re.fullmatch(r"[0-9a-f]{40}", ref) for ref in (commit, prereg)):
        raise ValueError("full lowercase code and protocol commits required")
    if (not re.fullmatch(r"[a-z0-9]+", account) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug)
            or stage not in ("calibration", "dev") or type(shard) is not int or shard not in range(4)):
        raise ValueError("invalid account, slug, stage or shard")
    shell = TEMPLATE.read_text(encoding="utf-8")
    for token, value in {"REF": commit, "PREREG": prereg, "STAGE": stage, "SHARD": str(shard)}.items():
        shell = shell.replace(f"__{token}__", value)
    if not shell.startswith("%%bash\n") or re.search(r"__[A-Z_]+__", shell):
        raise ValueError("unsubstituted notebook template")
    book = notebook(shell.removeprefix("%%bash\n"), "dev")
    book["cells"][0]["id"] = f"v10-{stage}-{shard}"
    metadata = {"id": f"{account}/{slug}", "title": slug, "code_file": "notebook.ipynb",
                "language": "python", "kernel_type": "notebook", "is_private": True,
                "enable_gpu": stage == "dev", "enable_internet": True,
                "dataset_sources": ["qktttttttttt/kineticscleaned"], "kernel_sources": [],
                "competition_sources": [], "model_sources": []}
    return book, metadata


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("commit", "prereg-commit", "account", "slug"):
        p.add_argument("--" + field, required=True)
    p.add_argument("--stage", choices=("calibration", "dev"), required=True)
    p.add_argument("--shard", type=int, choices=range(4), required=True)
    p.add_argument("--pool", type=Path, default=Path("D:/STUDY/LAB/pool.json"))
    p.add_argument("--write-only", action="store_true")
    args = p.parse_args()
    book, metadata = payload(args.commit, args.prereg_commit, args.account, args.slug, args.stage, args.shard)
    if not args.write_only:
        from ops.v10_spatial_gate import protocol, load_inputs
        plan, context = protocol(args.prereg_commit)
        if context["code_commit"] != args.commit:
            raise ValueError("push must use the inspected local HEAD")
        load_inputs(args.stage, plan, context)
    target = REPO / "ops/_push" / args.account / args.slug
    target.mkdir(parents=True, exist_ok=True)
    (target / "notebook.ipynb").write_text(json.dumps(book), encoding="utf-8")
    (target / "kernel-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    print(f"[V10] generated {metadata['id']} {args.stage} shard={args.shard}", flush=True)
    if args.write_only:
        return
    env = account_environment(args.pool, args.account)
    env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    require_inactive(metadata["id"], env)
    result = subprocess.run(kaggle_command() + ["kernels", "push", "-p", str(target)],
                            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    print(output.encode("ascii", "backslashreplace").decode("ascii"), flush=True)
    if result.returncode or "successfully pushed" not in output.lower():
        raise SystemExit(result.returncode or 1)


if __name__ == "__main__":
    main()
