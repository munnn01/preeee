from pathlib import Path
from collections import Counter
import hashlib
import json
import sys

repo = Path(r'D:\STUDY\LAB\pre_processor')
sys.path.insert(0,str(repo))
from ops.v11_spatial_dev import write_json, ARMS, MODELS, QPS
base = Path(__file__).resolve().parent
selection = json.loads((repo/'configs/v11_spatial/dev_selection.json').read_bytes())
audit = json.loads((base/'validation.json').read_bytes())
by_id = {}
for i in range(4):
    for line in (base/f'verified/shard{i}/shard_records.jsonl').read_bytes().splitlines():
        row = json.loads(line)
        if row['sequence_id'] in by_id:
            raise RuntimeError('duplicate source')
        by_id[row['sequence_id']] = row
rows = [by_id[s['sequence_id']] for s in selection['sources']]
if len(rows)!=200:
    raise RuntimeError('incomplete source count')
by_qp = {}
all_flips = {m:Counter() for m in MODELS}
for qp in QPS:
    items = [next(m for m in r['measurements'] if m['qp']==qp) for r in rows]
    fixed = [next(m for m in r['measurements'] if m['qp']==qp) for r in selection['sources']]
    changed = [i for i,p in enumerate(items) if p['arms']['v6']['name']!=p['arms']['v11']['name']]
    point = {'n_sources':len(items),'switches':len(changed),'arms':{},'v11_vs_v6_paired_correctness':{},
             'v11_vs_identity_paired_correctness':{}}
    for arm in ARMS:
        point['arms'][arm] = {'mean_bpp':sum(p['arms'][arm]['bpp'] for p in items)/len(items),
            'candidate_counts':dict(sorted(Counter(p['arms'][arm]['name'] for p in items).items())),
            'analyzers':{m:{'correct_count':sum(p['arms'][arm]['analyzers'][m]['correct'] for p in items),
                           'top1_pct':100*sum(p['arms'][arm]['analyzers'][m]['correct'] for p in items)/len(items)} for m in MODELS}}
    for model in MODELS:
        for anchor,field in (('v6','v11_vs_v6_paired_correctness'),('identity','v11_vs_identity_paired_correctness')):
            gains = losses = both_correct = both_wrong = 0
            for p in items:
                a = p['arms'][anchor]['analyzers'][model]['correct']
                b = p['arms']['v11']['analyzers'][model]['correct']
                gains += int(not a and b)
                losses += int(a and not b)
                both_correct += int(a and b)
                both_wrong += int(not a and not b)
            point[field][model] = {'gains':gains,'losses':losses,'net_correct':gains-losses,
                'both_correct':both_correct,'both_wrong':both_wrong,'top1_gap_pp':100*(gains-losses)/len(items)}
            if anchor=='v6':
                all_flips[model].update({'gains':gains,'losses':losses,'net_correct':gains-losses})
        if any(items[i]['arms']['v11']['analyzers'][model]!=items[i]['arms']['v6']['analyzers'][model]
               for i in range(len(items)) if i not in changed):
            raise RuntimeError('unchanged stream has different predictions')
    point['changed_pairs_proxy'] = {'n':len(changed),
        'mean_d112_reduction':sum(fixed[i]['proxy_candidates'][fixed[i]['choices']['v6']]['d112']-
                                   fixed[i]['proxy_candidates'][fixed[i]['choices']['v11']]['d112'] for i in changed)/len(changed) if changed else 0}
    by_qp[str(qp)] = point
diagnostic = {'kind':'v11_dev_descriptive_score_diagnostics','provenance':audit['provenance'],
    'dev_input_sha256':audit['dev_input_sha256'],'selection_sha256':audit['selection_sha256'],
    'validation_sha256':hashlib.sha256((base/'validation.json').read_bytes()).hexdigest(),
    'n_sources':200,'source_qp_pairs':1000,'by_qp':by_qp,
    'v11_vs_v6_correctness_flips_across_source_qp_pairs':{m:dict(v) for m,v in all_flips.items()},
    'bootstrap_scope':'descriptive counts only; no separate draws; BD metric intervals are in h265_result.json',
    'inference_limit':'Source-QP pairs share source video; counts across QPs are not independent trials.',
    'scope':'post-freeze descriptive assessment only; no policy tuning or holdout evaluation'}
write_json(base/'diagnostics.json',diagnostic)
for model in MODELS:
    print(model,'V11 vs V6 flips',dict(all_flips[model]),flush=True)
    for qp,p in by_qp.items():
        print(qp,'top1', {a:p['arms'][a]['analyzers'][model]['top1_pct'] for a in ARMS},
              'gap_vs_identity',p['v11_vs_identity_paired_correctness'][model]['top1_gap_pp'],
              'vs_v6',p['v11_vs_v6_paired_correctness'][model],flush=True)
