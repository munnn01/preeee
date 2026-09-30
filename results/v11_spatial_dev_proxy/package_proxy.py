from pathlib import Path
from collections import Counter
import hashlib
import json
import shutil
import subprocess

repo = Path(r'D:\STUDY\LAB\pre_processor')
stage = Path(__file__).resolve().parent
base = repo/'results/v11_spatial_dev_proxy'
if base.exists():
    raise RuntimeError('fresh proxy result package required')
selection_path = repo/'configs/v11_spatial/dev_selection.json'
selection = json.loads(selection_path.read_bytes())
if selection['n']!=200 or selection['provenance']['policy']!={'tau':0.0,'slack':0.05,'qp_mode':'all'}:
    raise RuntimeError('unexpected sealed input or policy')
def sha(body):
    return hashlib.sha256(body).hexdigest()
if sha(selection_path.read_bytes())!=selection_path.with_suffix('.sha256').read_text().split()[0]:
    raise RuntimeError('sealed selection hash mismatch')
def write(path, data):
    if path.exists():
        raise RuntimeError('fresh artifact required')
    raw=(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    path.write_bytes(raw)
    path.with_suffix('.sha256').write_bytes(f'{sha(raw)}  {path.name}\n'.encode('ascii'))
base.mkdir(parents=True)
(base/'archives').mkdir()
inventory=[]
download_inventory=json.loads((stage/'download_inventory.json').read_bytes())
for entry in download_inventory:
    i=entry['shard']
    source=stage/f'download/shard{i}/v11_dev_proxy_shard{i}.tgz'
    destination=base/f'archives/v11_dev_proxy_shard{i}.tgz'
    if sha(source.read_bytes())!=entry['archive_sha256']:
        raise RuntimeError('downloaded archive bytes changed')
    shutil.copyfile(source,destination)
    meta=json.loads((stage/f'verified/shard{i}/manifest.json').read_bytes())
    inventory.append({**entry,'path':destination.relative_to(base).as_posix(),
                      'n':meta['n'],'trial_encode_decode_count':meta['trial_encode_decode_count']})
context=selection['provenance']
transitions=Counter()
changed_sources=set()
by_qp={}
all_old,all_new,all_rate_old,all_rate_new=[],[],[],[]
for qp in (30,35,40,45,50):
    observations=[(s,next(m for m in s['measurements'] if m['qp']==qp)) for s in selection['sources']]
    old,new,r_old,r_new,r_identity=[],[],[],[],[]
    switches=0
    for s,m in observations:
        c=m['choices']
        old.append(m['proxy_candidates'][c['v6']]['d112'])
        new.append(m['proxy_candidates'][c['v11']]['d112'])
        r_old.append(m['bpp']['v6'])
        r_new.append(m['bpp']['v11'])
        r_identity.append(m['bpp']['identity'])
        if c['v6']!=c['v11']:
            transitions[f"{c['v6']} -> {c['v11']}"]+=1
            changed_sources.add(s['sequence_id'])
            switches+=1
    mean=lambda x:sum(x)/len(x)
    by_qp[str(qp)]={'n':len(observations),'switches':switches,
                   'mean_d112_v6':mean(old),'mean_d112_v11':mean(new),
                   'mean_d112_reduction':mean(old)-mean(new),
                   'mean_d112_reduction_relative_pct':100*(1-mean(new)/mean(old)),
                   'mean_bpp_identity':mean(r_identity),'mean_bpp_v6':mean(r_old),'mean_bpp_v11':mean(r_new),
                   'mean_bpp_v11_vs_v6_delta_pct':100*(mean(r_new)/mean(r_old)-1)}
    all_old+=old
    all_new+=new
    all_rate_old+=r_old
    all_rate_new+=r_new
mean=lambda x:sum(x)/len(x)
diagnostic={'kind':'v11_frozen_dev_proxy_diagnostic','provenance':context,
            'dev_input_sha256':selection['input_sha256'],'selection_sha256':sha(selection_path.read_bytes()),
            'n':selection['n'],'source_qp_pairs':len(all_old),'scope':'descriptive label-free DEV proxy; no fitting or selection of numeric policy',
            'trial_encode_decode_total':sum(e['trial_encode_decode_count'] for e in inventory),
            'switch_count':sum(transitions.values()),'changed_sources':len(changed_sources),
            'switches_qp45_50':by_qp['45']['switches']+by_qp['50']['switches'],
            'transitions':dict(sorted(transitions.items())),'by_qp':by_qp,
            'mean_d112_v6':mean(all_old),'mean_d112_v11':mean(all_new),
            'mean_d112_reduction':mean(all_old)-mean(all_new),
            'mean_d112_reduction_relative_pct':100*(1-mean(all_new)/mean(all_old)),
            'mean_bpp_v11_vs_v6_delta_pct':100*(mean(all_rate_new)/mean(all_rate_old)-1),
            'bootstrap_actual_draws':0,'bootstrap_scope':'not run for descriptive proxy; 2000 paired draws are planned for analyzer-score merge',
            'primary_bd_rate':'CHƯA ĐO','mc3_18':'CHƯA ĐO','ci95':'CHƯA ĐO','holdout':'CHƯA ĐO'}
write(base/'diagnostics.json',diagnostic)
write(base/'archive_inventory.json',{'kind':'v11_dev_proxy_archive_inventory','provenance':context,
     'dev_input_sha256':selection['input_sha256'],'selection_sha256':sha(selection_path.read_bytes()),
     'diagnostics_sha256':sha((base/'diagnostics.json').read_bytes()),'archives':inventory})
shutil.copyfile(stage/'package_proxy.py',base/'package_proxy.py')
write(base/'generator.json',{'kind':'v11_dev_proxy_package_generator','provenance':context,
     'generator_path':'package_proxy.py','generator_sha256':sha((base/'package_proxy.py').read_bytes()),
     'analysis_base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
     'scope':'external packaging and descriptive math only; policy and worker code unchanged'})
print(json.dumps(diagnostic,ensure_ascii=False,indent=2),flush=True)
