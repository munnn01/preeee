"""Publish one fresh private GPU notebook for frozen A/B MC3 scoring."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from .study import REPO,protocol,sha
from research.v12_lowqp.push import require_new_destination

def payload(commit,prereg,account,slug,shard):
    if (any(not re.fullmatch('[0-9a-f]{40}',v) for v in (commit,prereg))
        or not re.fullmatch('[a-z0-9]+',account) or not re.fullmatch('[a-z0-9][a-z0-9-]*',slug)
        or type(shard) is not int or shard not in range(4)): raise ValueError('invalid pinned destination')
    shell=(REPO/'kaggle/v12_mc3_cal_cell.sh').read_text(encoding='utf-8')
    for key,value in {'REF':commit,'PREREG':prereg,'SHARD':str(shard)}.items(): shell=shell.replace(f'__{key}__',value)
    if not shell.startswith('%%bash\n') or re.search('__[A-Z_]+__',shell): raise ValueError('invalid notebook template')
    book={'cells':[{'id':f'mc3-v12-cal-{shard}','cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
        'source':shell.splitlines(keepends=True)}],'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python'}},'nbformat':4,'nbformat_minor':5}
    meta={'id':f'{account}/{slug}','title':slug,'code_file':'notebook.ipynb','language':'python','kernel_type':'notebook',
        'is_private':True,'enable_gpu':True,'enable_internet':True,'dataset_sources':['qktttttttttt/kineticscleaned'],
        'kernel_sources':[],'competition_sources':[],'model_sources':[]}
    return book,meta

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('commit','prereg-commit','account','slug','payload-dir'): parser.add_argument('--'+name,required=True)
    parser.add_argument('--shard',type=int,choices=range(4),required=True)
    parser.add_argument('--pool',type=Path,default=Path('D:/STUDY/LAB/pool.json'))
    args=parser.parse_args()
    _,_,context=protocol(args.prereg_commit)
    if context['code_commit']!=args.commit: raise ValueError('local HEAD differs from worker pin')
    book,meta=payload(args.commit,args.prereg_commit,args.account,args.slug,args.shard)
    target=Path(args.payload_dir)
    if target.exists(): raise ValueError('fresh payload folder required')
    target.mkdir(parents=True)
    hashes={}
    for name,obj in (('notebook.ipynb',book),('kernel-metadata.json',meta)):
        raw=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
        (target/name).write_bytes(raw)
        hashes[name]=sha(raw)
    print(json.dumps({'generated':meta['id'],'payload_sha256':hashes}),flush=True)
    token=json.loads(args.pool.read_text(encoding='utf-8-sig')).get(args.account)
    if not isinstance(token,str) or not token.startswith('KGAT_'): raise ValueError('credential missing')
    os.environ['KAGGLE_API_TOKEN']=token
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        api=KaggleApi()
        api.authenticate()
        proof=require_new_destination(api,meta['id'])
    except Exception as exc:
        message=str(exc)
        if 'KGAT_' in message or token in message: raise RuntimeError('credential-bearing output blocked') from None
        raise RuntimeError('new destination check failed: '+message) from None
    print(json.dumps({'new_destination_proof':proof}),flush=True)
    env=os.environ.copy()
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,'-B','-c','from kaggle.cli import main; main()',
        'kernels','push','-p',str(target)],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    output=result.stdout+result.stderr
    if 'KGAT_' in output or token in output: raise RuntimeError('credential-bearing output blocked')
    print(output,flush=True)
    if result.returncode or 'successfully pushed' not in output.lower(): raise SystemExit(result.returncode or 1)

if __name__=='__main__': main()
