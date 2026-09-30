from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

repo = Path(r'D:\STUDY\LAB\pre_processor')
sys.path.insert(0, str(repo))
from ops.push_rcts_pilot import account_environment, kaggle_command

base = Path(__file__).resolve().parent
launch = json.loads((repo/'results/v11_spatial_dev_score_launch/launch.json').read_bytes())
pool = Path(r'D:\STUDY\LAB\pool.json')

def command(job, args):
    env = account_environment(pool, job['account'])
    env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run(kaggle_command()+args, env=env, capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    output = result.stdout + result.stderr
    if 'KGAT_' in output:
        raise RuntimeError('refusing credential-bearing output')
    return result.returncode, output

def status(job):
    code, output = command(job, ['kernels','status',job['handle']])
    return {**job, 'status_exit_code':code, 'status_api_output':output.strip()}

with ThreadPoolExecutor(max_workers=4) as executor:
    jobs = list(executor.map(status, launch['jobs']))
for job in jobs:
    print(job['status_api_output'], flush=True)
snapshot = base/'status.json'
if snapshot.exists():
    raise RuntimeError('fresh status artifact required')
snapshot.write_bytes((json.dumps({'checked_at_utc':datetime.now(timezone.utc).isoformat(),
    'provenance':launch['provenance'], 'jobs':jobs},ensure_ascii=False,indent=2)+'\n').encode())
if not all(j['status_exit_code']==0 and 'KernelWorkerStatus.COMPLETE' in j['status_api_output'] for j in jobs):
    raise SystemExit('Not all scoring jobs complete; do not merge incomplete curves.')
inventory = []
for job in jobs:
    i = job['shard']
    folder = base/f'download/shard{i}'
    if folder.exists():
        raise RuntimeError('fresh download directory required')
    folder.mkdir(parents=True)
    code, output = command(job, ['kernels','output',job['handle'],'-p',str(folder),
                                 '--file-pattern',rf'v11_dev_score_shard{i}\.tgz$','--force'])
    print(output, flush=True)
    path = folder/f'v11_dev_score_shard{i}.tgz'
    if code or not path.is_file():
        raise RuntimeError('archive download incomplete')
    prefix = f'outputs/v11_spatial_dev/score/shard{i}'
    expected = {'manifest.json','manifest.sha256','shard_records.jsonl','run.log'}
    target = base/f'verified/shard{i}'
    if target.exists():
        raise RuntimeError('fresh extraction directory required')
    content = {}
    with tarfile.open(path) as tar:
        for member in tar:
            name = member.name.rstrip('/')
            if member.isdir() and name==prefix:
                continue
            if (not member.isfile() or member.issym() or member.islnk()
                    or name not in {f'{prefix}/{n}' for n in expected}
                    or member.size>5_000_000):
                raise RuntimeError(f'unsafe/unexpected archive member: {name}')
            filename = name.removeprefix(prefix+'/')
            if filename in content:
                raise RuntimeError('duplicate archive member')
            body = tar.extractfile(member).read()
            if b'KGAT_' in body:
                raise RuntimeError('archive contains credential-like data')
            content[filename] = body
    if set(content)!=expected:
        raise RuntimeError('archive missing complete manifest or records')
    target.mkdir(parents=True)
    for name, body in content.items():
        (target/name).write_bytes(body)
    inventory.append({'shard':i, 'account':job['account'],'kaggle_url':job['url'],
        'archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'archive_bytes':path.stat().st_size,
        'files':{n:{'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)} for n,b in content.items()}})
(base/'download_inventory.json').write_bytes((json.dumps(inventory,indent=2)+'\n').encode())
print('Downloaded and safely extracted all four original scoring archives.',flush=True)
