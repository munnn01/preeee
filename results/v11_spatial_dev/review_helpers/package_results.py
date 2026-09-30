from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess

repo = Path(r'D:\STUDY\LAB\pre_processor')
review = Path(__file__).resolve().parent
out = repo/'results/v11_spatial_dev'

def sha(body):
    return hashlib.sha256(body).hexdigest()

def write(path,data):
    if path.exists() or path.with_suffix('.sha256').exists():
        raise RuntimeError(f'fresh artifact required: {path}')
    raw = (json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    path.write_bytes(raw)
    path.with_suffix('.sha256').write_bytes(f'{sha(raw)}  {path.name}\n'.encode('ascii'))

result = json.loads((out/'h265_result.json').read_bytes())
result_sha = sha((out/'h265_result.json').read_bytes())
if result_sha != (out/'h265_result.sha256').read_text().split()[0]:
    raise RuntimeError('merged result sidecar mismatch')
if {p.name for p in out.iterdir()} != {'h265_result.json','h265_result.sha256'}:
    raise RuntimeError('fresh result packaging required')
context = result['provenance']
for name in ('validation','diagnostics'):
    value = json.loads((review/f'{name}.json').read_bytes())
    if value['provenance']!=context or sha((review/f'{name}.json').read_bytes())!=(review/f'{name}.sha256').read_text().split()[0]:
        raise RuntimeError(f'{name} provenance/hash mismatch')
    shutil.copyfile(review/f'{name}.json',out/f'{name}.json')
    shutil.copyfile(review/f'{name}.sha256',out/f'{name}.sha256')
status = json.loads((review/'status.json').read_bytes())
write(out/'status_snapshot.json',status)
inventory = json.loads((review/'download_inventory.json').read_bytes())
(out/'archives').mkdir()
(out/'kaggle_logs').mkdir()
for entry in inventory:
    i = entry['shard']
    source = review/f'download/shard{i}/v11_dev_score_shard{i}.tgz'
    if sha(source.read_bytes())!=entry['archive_sha256']:
        raise RuntimeError('original download archive changed')
    archive = out/f'archives/{source.name}'
    shutil.copyfile(source,archive)
    meta = json.loads((review/f'verified/shard{i}/manifest.json').read_bytes())
    entry.update(path=archive.relative_to(out).as_posix(), n=meta['n'],
                 trial_encode_decode_count=meta['trial_encode_decode_count'])
logs = []
for i in range(4):
    candidates = list((review/f'download/shard{i}').glob('*.log'))
    if len(candidates)!=1:
        raise RuntimeError('expected one original Kaggle console log per shard')
    source = candidates[0]
    raw = source.read_bytes()
    if b'KGAT_' in raw:
        raise RuntimeError('refusing credential-bearing log')
    target = out/'kaggle_logs'/source.name
    shutil.copyfile(source,target)
    logs.append({'path':target.relative_to(out).as_posix(),'sha256':sha(raw),'bytes':len(raw)})
(out/'review_helpers').mkdir()
helpers = []
for name in ('check_download.py','audit_merge.py','diagnose.py','package_results.py'):
    target = out/'review_helpers'/name
    shutil.copyfile(review/name,target)
    helpers.append({'path':target.relative_to(out).as_posix(),'sha256':sha(target.read_bytes())})
diagnostic = json.loads((out/'diagnostics.json').read_bytes())
guard_deficits = {}
for qp,point in diagnostic['by_qp'].items():
    model_deficits = {}
    n = point['n_sources']
    for model in result['comparisons']['V11_vs_identity']:
        identity = point['arms']['identity']['analyzers'][model]['correct_count']
        v11 = point['arms']['v11']['analyzers'][model]['correct_count']
        minimum = math.ceil(identity-0.01*n-1e-9)
        model_deficits[model] = {'identity_correct':identity,'v11_correct':v11,
            'min_correct_to_satisfy_minus1pp_guard':minimum,'required_additional_net_correct':max(0,minimum-v11)}
    guard_deficits[qp] = {'n_sources':n,'models':model_deficits}
write(out/'guard_deficits.json',{'kind':'v11_dev_guard_deficit_calculation','provenance':context,
    'result_sha256':result_sha,'diagnostics_sha256':sha((out/'diagnostics.json').read_bytes()),
    'source_fingerprint':context['source_fingerprint'],'by_qp':guard_deficits,
    'formula':'minimum = ceil(identity_correct - 0.01*n); deficit = max(0, minimum - v11_correct)',
    'scope':'arithmetic diagnostic at fixed observed identity; not a measured improvement or new experiment',
    'bootstrap_scope':'no separate bootstrap for arithmetic counts',
    'interpretation':'Deficits at different QPs can concern the same source video; do not sum them as independent videos.'})
write(out/'archive_inventory.json',{'kind':'v11_dev_score_archive_inventory','provenance':context,
    'dev_input_sha256':result['input_sha256'],'selection_sha256':result['selection_sha256'],
    'result_sha256':result_sha,'validation_sha256':sha((out/'validation.json').read_bytes()),
    'diagnostics_sha256':sha((out/'diagnostics.json').read_bytes()),
    'guard_deficits_sha256':sha((out/'guard_deficits.json').read_bytes()),
    'status_snapshot_sha256':sha((out/'status_snapshot.json').read_bytes()),
    'archives':inventory,'kaggle_logs':logs,'review_helpers':helpers})
write(out/'generator.json',{'kind':'v11_dev_result_package_generator','provenance':context,
    'analysis_base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    'generator_path':'review_helpers/package_results.py','generator_sha256':sha(Path(__file__).read_bytes()),
    'result_sha256':result_sha,
    'scope':'packaging and post-freeze descriptive arithmetic only; selector, metrics and bootstrap unchanged'})
print(json.dumps({'packaged':str(out),'result_sha256':result_sha,'archives':len(inventory),
    'mc3_guard_deficits':{qp:p['models']['mc3_18']['required_additional_net_correct'] for qp,p in guard_deficits.items()}},indent=2),flush=True)
