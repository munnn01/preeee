from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

repo = Path(r'D:\STUDY\LAB\pre_processor')
sys.path.insert(0, str(repo))
from ops import v11_spatial_dev as dev

base = Path(__file__).resolve().parent
plan, context = dev.protocol()
data, input_sha = dev.load_input(plan, context)
selected, selection_sha = dev.load_selection(data, context, input_sha)
folders = [base/f'verified/shard{i}' for i in range(4)]
rows, manifests = dev.load_bundles(folders, 'v11_dev_score_shard', selected['sources'], context,
                                 {'input_sha256':input_sha, 'selection_sha256':selection_sha})
launch = json.loads((repo/'results/v11_spatial_dev_score_launch/launch.json').read_bytes())
expected_commit = launch['selection_commit']
if any(m['provenance']['code_commit'] != expected_commit for m in manifests):
    raise RuntimeError('worker revision differs from the globally committed selection')
weights = manifests[0]['analyzer_weights_sha256']
versions = manifests[0]['versions']
if any(m['analyzer_weights_sha256'] != weights or m['versions'] != versions or m['device'] != 'cuda'
       or m['analyzers'] != list(dev.MODELS) for m in manifests):
    raise RuntimeError('analyzer weights/environment/device differ across shards')
if any(m['trial_encode_decode_count'] != j['planned_unique_encode_decode_trials']
       for m,j in zip(manifests,launch['jobs'],strict=True)):
    raise RuntimeError('trial counts differ from submission plan')
audit = {'kind':'v11_dev_score_validation','provenance':context,
    'validated_at_utc':datetime.now(timezone.utc).isoformat(), 'scoring_worker_commit':expected_commit,
    'dev_input_sha256':input_sha, 'selection_sha256':selection_sha,
    'n_sources':len(rows), 'shards':4, 'n_per_shard':[m['n'] for m in manifests],
    'trial_encode_decode_count':[m['trial_encode_decode_count'] for m in manifests],
    'trial_encode_decode_total':sum(m['trial_encode_decode_count'] for m in manifests),
    'analyzer_weights_sha256':weights, 'versions':versions, 'device':'cuda',
    'checks':{'four_complete_disjoint_shards':True, 'source_ids_and_source_bytes_match_plan':True,
        'manifest_records_and_sidecar_hashes_match':True, 'policy_and_all_choices_committed_before_scoring':True,
        'choices_recompute_exactly_from_frozen_policy_and_proxy':True,
        'source_qp_bpp_and_byte_count_match_locked_streams':True, 'decoded_pixels_match_proxy_for_shared_candidates':True,
        'five_arms_three_analyzers_all_five_qps':True, 'same_candidate_reuse_has_identical_values':True,
        'correctness_matches_prediction_and_canonical_label':True, 'same_weights_versions_worker_commit_across_shards':True,
        'all_encode_decode_trials_counted_as_planned':True},
    'scope':'reused DEV assessment; no fitting, selection or holdout evaluation',
    'timing_scope':'evaluation only; full selector cost CHƯA ĐO'}
dev.write_json(base/'validation.json',audit)
print(json.dumps({'validation':'PASS','n':len(rows),'trials':audit['trial_encode_decode_total'],
                  'versions':versions,'merge':'Starting unchanged 2000 paired source-video draws for all comparisons.'},
                 ensure_ascii=False,indent=2),flush=True)
result = dev.merge(folders,repo/'results/v11_spatial_dev/h265_result.json',selected,context,input_sha,selection_sha)
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
