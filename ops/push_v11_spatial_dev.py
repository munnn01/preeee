"""Publish a private, revision-pinned V11 DEV proxy or score shard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

from ops.push_dual_codec_search import require_inactive
from ops.push_rcts_pilot import account_environment, kaggle_command, notebook

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / 'kaggle/v11_spatial_dev_cell.sh'


def payload(commit: str, account: str, slug: str, shard: int, phase: str) -> tuple[dict, dict]:
    if (not re.fullmatch('[0-9a-f]{40}', commit) or not re.fullmatch('[a-z0-9]+', account)
            or not re.fullmatch('[a-z0-9][a-z0-9-]*', slug) or type(shard) is not int
            or shard not in range(4) or phase not in ('proxy', 'score')):
        raise ValueError('invalid pinned revision, destination, phase or shard')
    shell = TEMPLATE.read_text(encoding='utf-8')
    for token, value in {'REF': commit, 'SHARD': str(shard), 'PHASE': phase}.items():
        shell = shell.replace(f'__{token}__', value)
    if not shell.startswith('%%bash\n') or re.search(r'__[A-Z_]+__', shell):
        raise ValueError('unsubstituted notebook token')
    book = notebook(shell.removeprefix('%%bash\n'), 'dev')
    book['cells'][0]['id'] = f'v11-dev-{phase}-{shard}'
    meta = {'id': f'{account}/{slug}', 'title': slug, 'code_file': 'notebook.ipynb',
            'language': 'python', 'kernel_type': 'notebook', 'is_private': True,
            'enable_gpu': phase == 'score', 'enable_internet': True,
            'dataset_sources': ['qktttttttttt/kineticscleaned'], 'kernel_sources': [],
            'competition_sources': [], 'model_sources': []}
    return book, meta


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('commit', 'account', 'slug'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--shard', type=int, choices=range(4), required=True)
    parser.add_argument('--phase', choices=('proxy', 'score'), required=True)
    parser.add_argument('--pool', type=Path, default=Path('D:/STUDY/LAB/pool.json'))
    parser.add_argument('--write-only', action='store_true')
    args = parser.parse_args()
    book, meta = payload(args.commit, args.account, args.slug, args.shard, args.phase)
    if not args.write_only:
        from ops.v11_spatial_dev import protocol, load_input, load_selection
        plan, context = protocol()
        if context['code_commit'] != args.commit:
            raise ValueError('push must use inspected local HEAD')
        data, input_sha = load_input(plan, context)
        if args.phase == 'score':
            load_selection(data, context, input_sha)  # Requires all 200 choices committed.
    target = REPO / 'ops/_push' / args.account / args.slug
    target.mkdir(parents=True, exist_ok=True)
    (target / 'notebook.ipynb').write_text(json.dumps(book), encoding='utf-8')
    (target / 'kernel-metadata.json').write_text(json.dumps(meta), encoding='utf-8')
    print(f"[V11] generated {meta['id']} phase={args.phase} shard={args.shard}", flush=True)
    if args.write_only:
        return
    env = account_environment(args.pool, args.account)
    env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
    require_inactive(meta['id'], env)
    result = subprocess.run(kaggle_command() + ['kernels', 'push', '-p', str(target)],
                            env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    output = result.stdout + result.stderr
    print(output.encode('ascii', 'backslashreplace').decode('ascii'), flush=True)
    if result.returncode or 'successfully pushed' not in output.lower():
        raise SystemExit(result.returncode or 1)


if __name__ == '__main__':
    main()
