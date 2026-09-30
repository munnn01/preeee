"""Score both committed V12 policies on MC3 after decoding locked CAL streams."""
import argparse
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import time
import cv2
import numpy as np
import torch
import torchvision
from torchvision.models.video import MC3_18_Weights
from research.v12_lowqp.study import REPO,git,committed,sha,write_json,source_paths,read_clip,fingerprint
from research.v12_lowqp.paired_metrics import summarize
from research.v12_lowqp.teacher import state_hash
from src.codecs.standard import StandardCodec
from src.models.codec_search import CANDIDATES,make_candidates,normalized_bpp
from src.tasks.action_recognition import ActionRecognitionAnalyzer,kinetics_categories,kinetics_category_index,_canon

CONFIG='configs/v12_mc3_audit/protocol.json'
QPS=(30,35,40,45,50)
ARMS=('identity','v6','area112','v12a','v12b')
MODEL='mc3_18'

def validate_input(data,cfg):
    if (set(data)!={'kind','scope','parent_freezes','sources','n','qps','shards'}
        or data['kind']!='v12_frozen_mc3_CAL_selection' or data['parent_freezes']!=cfg['parent_freezes']
        or data['n']!=200 or data['shards']!=4 or data['qps']!=list(QPS)):
        raise ValueError('selection/index schema changed')
    sources=data['sources']
    ids=[s['sequence_id'] for s in sources]
    hashes=[s['source_sha256'] for s in sources]
    if (len(sources)!=200 or len(set(Path(i).stem for i in ids))!=200 or len(set(hashes))!=200
        or fingerprint(ids)!=cfg['source_fingerprint']):
        raise ValueError('source cohort/fingerprint changed')
    for source in sources:
        if (set(source)!={'sequence_id','source_sha256','measurements'} or not re.fullmatch('[0-9a-f]{64}',source['source_sha256'])
            or len(source['measurements'])!=5):
            raise ValueError('invalid or outcome-bearing source index')
        for p,qp in zip(source['measurements'],QPS,strict=True):
            if (set(p)!={'qp','arms','streams'} or p['qp']!=qp or set(p['arms'])!=set(ARMS)
                or p['arms']['identity']!='identity128' or p['arms']['area112']!='area112'
                or set(p['streams'])!=set(p['arms'].values()) or any(n not in CANDIDATES for n in p['streams'])):
                raise ValueError('arm/stream/QP selection changed')
            if qp>=45 and any(p['arms'][a]!=p['arms']['v6'] for a in ('v12a','v12b')):
                raise ValueError('frozen high-QP V6 retention changed')
            for value in p['streams'].values():
                if (set(value)!={'bpp','coded_bytes','decoded_sha256'} or type(value['coded_bytes']) is not int
                    or value['coded_bytes']<=0 or type(value['bpp']) not in (int,float) or not math.isfinite(value['bpp'])
                    or abs(value['bpp']-value['coded_bytes']*8/(16*128*128))>1e-9
                    or not re.fullmatch('[0-9a-f]{64}',value['decoded_sha256'])):
                    raise ValueError('frozen bytes/pixels invalid')

def protocol(ref):
    if not re.fullmatch('[0-9a-f]{40}',ref): raise ValueError('full preregistration commit required')
    git('merge-base','--is-ancestor',ref,'HEAD')
    raw=committed(CONFIG)
    if committed(CONFIG,ref)!=raw: raise ValueError('registered config changed')
    cfg=json.loads(raw)
    doc=committed(cfg['preregistration_path'])
    if doc!=committed(cfg['preregistration_path'],ref) or b'\nPREREGISTRATION_LOCKED: true\n' not in doc or sha(raw).encode() not in doc:
        raise ValueError('MC3 registration changed or not locked')
    if (cfg['n']!=200 or cfg['shards']!=4 or cfg['qps']!=list(QPS) or cfg['arms']!=list(ARMS)
        or cfg['seed']!=20261010 or cfg['bootstrap_draws']!=2000 or cfg['codec']!='h265' or cfg['preset']!='medium'
        or cfg['analyzer']['name']!=MODEL or cfg['analyzer']['weights']!='KINETICS400_V1' or cfg['analyzer']['clip_size']!=112):
        raise ValueError('registered constants changed')
    index=committed(cfg['input_path'])
    if index!=committed(cfg['input_path'],ref) or sha(index)!=cfg['input_sha256']:
        raise ValueError('frozen index changed')
    for path,value in ((CONFIG,sha(raw)),(cfg['input_path'],sha(index))):
        if (REPO/path).with_suffix('.sha256').read_text().split()!=[value,Path(path).name]:
            raise ValueError('config/index sidecar changed')
    for path,value in cfg['core_git_blob_sha256'].items():
        if sha(committed(path))!=value: raise ValueError('core/metric/bootstrap changed: '+path)
    frozen=cfg['parent_freezes']['v12a']
    git('merge-base','--is-ancestor',frozen['freeze_commit'],ref)
    if sha(committed('results/v12_lowqp/frozen_policy.json',frozen['freeze_commit']))!=frozen['frozen_policy_sha256']:
        raise ValueError('parent A freeze changed')
    data=json.loads(index)
    validate_input(data,cfg)
    watched=['research/v12_mc3_audit','research/v12_lowqp','kaggle/v12_mc3_cal_cell.sh',*cfg['core_git_blob_sha256']]
    git('diff','--exit-code','HEAD','--',*watched)
    context={'experiment':cfg['experiment'],'scope':cfg['scope'],'repository_url':cfg['repository_url'],
        'code_commit':git('rev-parse','HEAD').decode().strip(),'code_fingerprint':sha(git('ls-tree','-r','HEAD','--',*watched)),
        'preregistration_commit':ref,'preregistration_sha256':sha(doc),'protocol_sha256':sha(raw),
        'selection_sha256':sha(index),'source_fingerprint':cfg['source_fingerprint'],'parent_freezes':cfg['parent_freezes'],
        'model':cfg['analyzer'],'bootstrap_unit':cfg['bootstrap_unit'],'bootstrap_seed':cfg['seed'],'bootstrap_draws':2000,
        'metric_sha256':cfg['core_git_blob_sha256']['src/metrics/bd_rate.py'],
        'bootstrap_sha256':cfg['core_git_blob_sha256']['research/v12_lowqp/paired_metrics.py']}
    return cfg,data,context

def label_for(source):
    name=_canon(Path(source['sequence_id']).parent.name)
    mapping=kinetics_category_index(MODEL)
    if name not in mapping: raise ValueError('source label absent from frozen Kinetics ordering')
    return mapping[name]

def validate_record(row,source,label):
    if (set(row)!={'sequence_id','source_sha256','label','measurements'} or any(row[k]!=source[k] for k in ('sequence_id','source_sha256'))
        or row['label']!=label or len(row['measurements'])!=5):
        raise ValueError('source/label/record schema mismatch')
    for point,fixed in zip(row['measurements'],source['measurements'],strict=True):
        if (set(point)!={'qp','arms','streams'} or point['qp']!=fixed['qp'] or point['arms']!=fixed['arms']
            or set(point['streams'])!=set(fixed['streams'])): raise ValueError('record stream/choice mismatch')
        for name,item in point['streams'].items():
            expected=fixed['streams'][name]
            if (set(item)!={'bpp','coded_bytes','decoded_sha256','prediction','correct','encode_decode_s','inference_s'}
                or any(item[k]!=expected[k] for k in ('bpp','coded_bytes','decoded_sha256'))
                or type(item['prediction']) is not int or not 0<=item['prediction']<400
                or type(item['correct']) is not bool or item['correct']!=(item['prediction']==label)
                or any(type(item[k]) not in (int,float) or not math.isfinite(item[k]) or item[k]<0 for k in ('encode_decode_s','inference_s'))):
                raise ValueError('wrong decoded pixels, bytes, score or timing')

def evaluate_source(source,clip,codec,predict,label):
    variants=make_candidates(clip)
    points=[]
    for fixed in source['measurements']:
        streams={}
        for name,expected in fixed['streams'].items():
            candidate=variants[name]
            start=time.perf_counter()
            decoded,native=codec._encode_decode_clip(candidate,qp=fixed['qp'])
            elapsed=time.perf_counter()-start
            bpp=normalized_bpp(native,*candidate.shape[1:3])
            coded=round(bpp*16*128*128/8)
            pixels=sha(decoded.tobytes())
            if (abs(bpp-expected['bpp'])>1e-9 or coded!=expected['coded_bytes'] or pixels!=expected['decoded_sha256']):
                raise ValueError('codec reconstruction differs from frozen stream BEFORE inference')
            prediction,inference_s=predict(decoded)
            streams[name]={**expected,'prediction':prediction,'correct':bool(prediction==label),
                'encode_decode_s':elapsed,'inference_s':inference_s}
        points.append({'qp':fixed['qp'],'arms':fixed['arms'],'streams':streams})
    row={k:source[k] for k in ('sequence_id','source_sha256')}|{'label':label,'measurements':points}
    validate_record(row,source,label)
    return row

def run_shard(root,shard,out,cfg,data,context):
    if type(shard) is not int or shard not in range(4) or out.exists(): raise ValueError('fresh shard output required')
    sources=data['sources'][shard::4]
    paths=source_paths(root,sources)
    torch.manual_seed(cfg['seed'])
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
    if not torch.cuda.is_available(): raise ValueError('registered GPU worker has no CUDA')
    spec=cfg['analyzer']
    weights=MC3_18_Weights.KINETICS400_V1
    categories=kinetics_categories(MODEL)
    if (weights.url!=spec['url'] or categories!=kinetics_categories('r3d_18')
        or sha(json.dumps(categories,ensure_ascii=False,separators=(',',':')).encode())!=spec['categories_sha256']):
        raise ValueError('analyzer URL or category ordering changed')
    labels={s['sequence_id']:label_for(s) for s in sources}
    analyzer=ActionRecognitionAnalyzer(MODEL,clip_size=112).freeze()
    checkpoint=Path(torch.hub.get_dir())/'checkpoints'/spec['url'].rsplit('/',1)[-1]
    if sha(checkpoint.read_bytes())!=spec['checkpoint_sha256'] or state_hash(analyzer.net)!=spec['state_sha256']:
        raise ValueError('MC3 checkpoint/state hash mismatch')
    analyzer.to('cuda')
    def predict(decoded):
        torch.cuda.synchronize()
        start=time.perf_counter()
        video=torch.from_numpy(decoded.transpose(3,0,1,2).copy())[None].float().div_(255).to('cuda')
        with torch.inference_mode(): logits=analyzer.predict(video)
        if logits.shape!=(1,400) or not torch.isfinite(logits).all(): raise ValueError('invalid MC3 logits')
        prediction=int(logits.argmax(1).item())
        torch.cuda.synchronize()
        return prediction,time.perf_counter()-start
    out.mkdir(parents=True)
    raw=out/'shard_records.jsonl'
    codec=StandardCodec('h265',preset='medium',strict_decode=True)
    trials=0
    with raw.open('wb') as handle:
        for number,source in enumerate(sources,1):
            row=evaluate_source(source,read_clip(paths[source['sequence_id']]),codec,predict,labels[source['sequence_id']])
            handle.write((json.dumps(row,sort_keys=True,allow_nan=False)+'\n').encode())
            handle.flush()
            trials+=sum(len(p['streams']) for p in row['measurements'])
            print(f'[MC3 V12] shard={shard} {number}/50 unique_trials={trials}',flush=True)
    write_json(out/'manifest.json',{'kind':'v12_mc3_frozen_CAL_shard','provenance':context,'shard':shard,'shards':4,'n':50,
        'source_ids':[s['sequence_id'] for s in sources],'records_sha256':sha(raw.read_bytes()),'unique_encode_decode_inference_trials':trials,
        'actual_bootstrap_draws':0,'model_checkpoint_sha256':sha(checkpoint.read_bytes()),'model_state_sha256':state_hash(analyzer.net),
        'device':'cuda','gpu_name':torch.cuda.get_device_name(),'versions':{'python':platform.python_version(),
        'torch':torch.__version__,'torchvision':torchvision.__version__,'numpy':np.__version__,'opencv':cv2.__version__,
        'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0]},
        'timing_scope':'MC3 evaluation of frozen selected streams; not full selector overhead'})
    return {'shard':shard,'n':50,'unique_trials':trials}

def load_shards(folders,cfg,data,context):
    if len(folders)!=4: raise ValueError('four complete shards required')
    records,metas,commits={},{},set()
    for folder in folders:
        meta=json.loads((folder/'manifest.json').read_bytes())
        shard=meta.get('shard')
        if type(shard) is not int or shard not in range(4) or shard in metas: raise ValueError('duplicate/invalid shard')
        assigned=data['sources'][shard::4]
        prov=meta.get('provenance',{})
        if (meta.get('kind')!='v12_mc3_frozen_CAL_shard' or meta.get('n')!=50 or meta.get('shards')!=4
            or meta.get('source_ids')!=[s['sequence_id'] for s in assigned]
            or any(prov.get(k)!=v for k,v in context.items() if k!='code_commit')
            or (folder/'manifest.sha256').read_text().split()!=[sha((folder/'manifest.json').read_bytes()),'manifest.json']
            or meta.get('records_sha256')!=sha((folder/'shard_records.jsonl').read_bytes()) or meta.get('actual_bootstrap_draws')!=0
            or meta.get('device')!='cuda' or meta.get('model_checkpoint_sha256')!=cfg['analyzer']['checkpoint_sha256']
            or meta.get('model_state_sha256')!=cfg['analyzer']['state_sha256']): raise ValueError('shard provenance/hash mismatch')
        worker=prov.get('code_commit','')
        if not re.fullmatch('[0-9a-f]{40}',worker): raise ValueError('missing worker commit')
        git('merge-base','--is-ancestor',worker,'HEAD')
        commits.add(worker)
        rows=[json.loads(line) for line in (folder/'shard_records.jsonl').read_bytes().splitlines()]
        if len(rows)!=50: raise ValueError('incomplete MC3 shard')
        for row,source in zip(rows,assigned,strict=True):
            validate_record(row,source,label_for(source))
            if row['sequence_id'] in records: raise ValueError('duplicate MC3 source')
            records[row['sequence_id']]=row
        if meta['unique_encode_decode_inference_trials']!=sum(len(p['streams']) for row in rows for p in row['measurements']):
            raise ValueError('unique trial count mismatch')
        metas[shard]={**meta,'manifest_sha256':sha((folder/'manifest.json').read_bytes())}
    if len(commits)!=1 or len(records)!=200 or any(m['versions']!=metas[0]['versions'] for m in metas.values()):
        raise ValueError('mixed workers/environments or cohort size')
    return [records[s['sequence_id']] for s in data['sources']],[metas[s] for s in range(4)]

def bootstrap_rows(records):
    return [{'sequence_id':r['sequence_id'],'measurements':[{'qp':p['qp'],'arms':{arm:{'bpp':p['streams'][name]['bpp'],
        'analyzers':{MODEL:{'correct':p['streams'][name]['correct']}}} for arm,name in p['arms'].items()}}
        for p in r['measurements']]} for r in records]

def component_gate(entry):
    metrics,boots=entry['metrics'],entry['bootstrap']
    valid=all(x['valid_draws']>=1900 and x['ci95'] is not None and all(math.isfinite(v) for v in x['ci95']) for x in boots.values())
    if not valid: return 'INCONCLUSIVE_INSUFFICIENT_DRAWS'
    return ('PASS_ON_REUSED_CAL_ONLY' if metrics['bd_rate_top1_pct'] is not None and metrics['bd_rate_top1_pct']<0
        and boots['bd_rate_top1_pct']['ci95'][1]<=1 and metrics['bd_accuracy_top1_pp'] is not None
        and metrics['bd_accuracy_top1_pp']>0 and metrics['min_same_qp_top1_gap_pp']>=-1-1e-9 else 'FAIL_ON_REUSED_CAL')

def merge(folders,out,cfg,data,context):
    if out.exists() or out.with_suffix('.sha256').exists(): raise ValueError('fresh merged result required')
    records,metas=load_shards(folders,cfg,data,context)
    rows=bootstrap_rows(records)
    draws=np.random.default_rng(cfg['seed']).integers(0,200,size=(2000,200))
    comparisons={}
    for name,anchor,trial in cfg['comparisons']:
        print('[bootstrap] '+name,flush=True)
        comparisons[name]=summarize(rows,anchor,trial,MODEL,draws)
    report={'kind':'v12_mc3_CAL_diagnostic_result','provenance':context,'n':200,'qps':list(QPS),
        'source_manifests':metas,'sources':[{k:r[k] for k in ('sequence_id','source_sha256')} for r in records],
        'unique_trials':sum(m['unique_encode_decode_inference_trials'] for m in metas),'comparisons':comparisons,
        'mc3_component':{arm:component_gate(comparisons[arm+'_vs_identity']) for arm in ('v12a','v12b')},
        'actual_bootstrap_draws':2000,'bootstrap_interpretation':'descriptive post-freeze audit on reused CAL; no independent confirmation',
        'policy_selection_using_MC3':False,'fresh_dev':'CHƯA ĐO','holdout':'CHƯA ĐO','original_minus15_gate':'unchanged'}
    write_json(out,report)
    return {'n':200,'unique_trials':report['unique_trials'],'mc3_component':report['mc3_component'],'result_sha256':sha(out.read_bytes())}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prereg-commit',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('preflight')
    s=sub.add_parser('shard')
    s.add_argument('--source-root',type=Path,required=True)
    s.add_argument('--shard',type=int,choices=range(4),required=True)
    s.add_argument('--out-dir',type=Path,required=True)
    m=sub.add_parser('merge')
    m.add_argument('--shard-dir',type=Path,action='append',required=True)
    m.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    cfg,data,context=protocol(args.prereg_commit)
    result=(context if args.command=='preflight' else run_shard(args.source_root,args.shard,args.out_dir,cfg,data,context)
        if args.command=='shard' else merge(args.shard_dir,args.out,cfg,data,context))
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),flush=True)

if __name__=='__main__': main()
