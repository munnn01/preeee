"""Two-stage V11 reused-DEV evaluation; global choices precede all scoring."""
from __future__ import annotations

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

from ops import v11_spatial_cal as cal
from ops.dual_codec_search import digest
from ops.v5_dev_agreement import load_locked_dev_cache
from ops.v6_dev_residual import predicted_measurements, select_residual
from ops.v7_pixel_proxy import find_planned_videos, sha256
from ops.v8_motion_pilot import summarize
from ops.v10_spatial_gate import engineering_gate, read_clip
from ops.v11_spatial_policy import QPS, choose, validate_policy
from src.codecs.standard import StandardCodec, ffmpeg_available
from src.models.codec_search import CANDIDATES, make_candidates, normalized_bpp
from src.models.dual_codec_search import observations

REPO = cal.REPO
PREREG = '00951bd52efeb3c64feb62254cef2aa484431e60'
FREEZE_COMMIT = '49fb15f6de86f09c6c0a845098cbbf199c405c03'
FREEZE_SHA = '280c926a65458a00b192ed1cd0a44e6b341ac6a4f049c96852d5b0e15a410a0e'
INPUT = 'configs/v11_spatial/dev_input.json'
SELECTION = 'configs/v11_spatial/dev_selection.json'
MODELS = ('r2plus1d_18', 'r3d_18', 'mc3_18')
ARMS = ('identity', 'area112', 'v2', 'v6', 'v11')
SHARDS, SEED, DRAWS = 4, 20261008, 2000
UNIT = 'source video; all QPs, arms and analyzers paired'


def protocol() -> tuple[dict, dict]:
    plan, _, context = cal.protocol(PREREG)
    cal.git('merge-base', '--is-ancestor', FREEZE_COMMIT, 'HEAD')
    frozen = cal.committed(cal.RESULT, FREEZE_COMMIT)
    if cal.hash_bytes(frozen) != FREEZE_SHA or cal.committed(cal.RESULT) != frozen:
        raise ValueError('V11 CAL freeze changed')
    policy = json.loads(frozen)['selected_policy']
    validate_policy(policy)
    if json.loads(frozen)['status'] != 'FREEZE_BEFORE_DEV':
        raise ValueError('CAL did not authorize DEV')
    for path in ('ops/v11_spatial_dev.py', 'ops/push_v11_spatial_dev.py', 'kaggle/v11_spatial_dev_cell.sh'):
        cal.committed(path)
    cal.git('diff', '--exit-code', 'HEAD', '--', 'ops', 'src', 'kaggle/v11_spatial_dev_cell.sh')
    for relative, expected in plan['input_sha256'].items():
        if cal.hash_bytes(cal.committed(relative)) != expected:
            raise ValueError(f'locked historical input changed: {relative}')
    sources = plan['stages']['dev']
    ids = [s['sequence_id'] for s in sources]
    hashes = [s['source_sha256'] for s in sources]
    if (len(sources) != 200 or len(set(Path(k).stem for k in ids)) != 200
            or len(set(hashes)) != 200 or digest(ids) != plan['source_fingerprints']['dev']
            or set(Path(k).stem for k in ids) & {Path(s['sequence_id']).stem for s in plan['stages']['calibration']}
            or set(hashes) & {s['source_sha256'] for s in plan['stages']['calibration']}):
        raise ValueError('DEV source plan changed or overlaps CAL')
    return plan, {**context, 'experiment': 'v11_h265_frozen_reused_dev',
                  'code_fingerprint': cal.hash_bytes(cal.git('ls-tree', '-r', 'HEAD', '--', 'ops', 'src', 'kaggle/v11_spatial_dev_cell.sh')),
                  'calibration_commit': FREEZE_COMMIT, 'calibration_sha256': FREEZE_SHA,
                  'policy': policy, 'source_fingerprint': plan['source_fingerprints']['dev'],
                  'bootstrap_seed': SEED, 'bootstrap_draws': DRAWS, 'bootstrap_unit': UNIT,
                  'scope': 'reused DEV development; no TEST or holdout'}


def write_json(path: Path, value: dict) -> None:
    if path.exists() or path.with_suffix('.sha256').exists():
        raise ValueError(f'fresh artifact required: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    path.write_bytes(body)
    path.with_suffix('.sha256').write_bytes(f'{cal.hash_bytes(body)}  {path.name}\n'.encode('ascii'))


def label_free_object(value: dict) -> dict:
    # Historical correctness is never exposed to selector/model prediction.
    return {k: v for k, v in value.items() if k not in ('label', 'target', 'correct', 'cross_correct')}


def prepare_input(cache_root: Path, plan: dict, context: dict) -> dict:
    if cache_root.name != 'h265' or cache_root.parent.name != 'dual_codec_search_v2':
        raise ValueError('only the locked historical H.265 development cache is allowed')
    lock, lock_sha = load_locked_dev_cache()
    expected = lock['input_provenance']['h265']
    for name, key in (('manifest.json', 'manifest_sha256'), ('risk_model.json', 'risk_model_sha256'),
                      ('frozen_policy.json', 'frozen_policy_sha256')):
        if sha256(cache_root / name) != expected[key]:
            raise ValueError(f'historical {name} changed')
    manifest = json.loads((cache_root / 'manifest.json').read_bytes())
    old_plan = json.loads(cal.committed('configs/v7_dev_proxy_plan.json'))
    if manifest['split_ids'] != old_plan['stage_ids'] or manifest['split_fingerprints'] != old_plan['source_fingerprints']:
        raise ValueError('historical split changed')
    risk = json.loads((cache_root / 'risk_model.json').read_bytes())
    old_policy = json.loads((cache_root / 'frozen_policy.json').read_bytes())
    if old_policy['manifest_sha256'] != digest(manifest) or old_policy['risk_sha256'] != digest(risk):
        raise ValueError('historical V2 policy provenance changed')
    files = sorted((cache_root / 'cache/dev').glob('clip_*.json'))
    tree = cal.hash_bytes(''.join(f'{p.name}\t{sha256(p)}\n' for p in files).encode())
    if len(files) != 200 or tree != expected['cache_tree_sha256']['dev']:
        raise ValueError('historical DEV records changed')
    rows = {}
    for path in files:
        row = json.loads(path.read_bytes(), object_hook=label_free_object)
        key = row['sequence_id']
        if key in rows or row['codec'] != 'h265' or row['cache_key'] != digest(manifest):
            raise ValueError('invalid historical source/cache key')
        if [m['qp'] for m in row['measurements']] != list(QPS):
            raise ValueError('historical QP order changed')
        for item in row['measurements']:
            item['candidates'] = observations(item['candidates'])
            if [c['name'] for c in item['candidates']] != list(CANDIDATES):
                raise ValueError('historical candidate order changed')
        rows[key] = row
    ids = [s['sequence_id'] for s in plan['stages']['dev']]
    if set(rows) != set(ids):
        raise ValueError('historical DEV cohort differs from pinned plan')
    # Load only pinned policy/model files, without reopening historical outcome reports.
    import joblib
    cfg = json.loads(cal.committed('configs/v6_h265_frozen/manifest.json'))
    v6_policy = cfg['policy']
    if digest(v6_policy) != cfg['policy_digest']:
        raise ValueError('frozen V6 policy digest changed')
    models = {}
    for model in MODELS[:2]:
        models[model] = {}
        for event in ('harm', 'gain'):
            path = REPO / cfg['model_paths'][model][event]
            if sha256(path) != cfg['model_sha256'][model][event]:
                raise ValueError('frozen V6 model bytes changed')
            models[model][event] = joblib.load(path)
    prepared = predicted_measurements([rows[k] for k in ids], risk, old_policy['selected_policy'], models)
    reference = json.loads(cal.committed('configs/v7_mc3_dev_selection.json'))
    if [r['sequence_id'] for r in reference['sources']] != ids:
        raise ValueError('historical frozen V6 source order changed')
    sources = []
    for source, video, ref in zip(plan['stages']['dev'], prepared, reference['sources'], strict=True):
        measurements = []
        for (measurement, obs, base, probabilities), previous in zip(video, ref['measurements'], strict=True):
            v6 = CANDIDATES[select_residual(obs, base, probabilities, v6_policy)]
            if previous['v6'] != v6 or previous['qp'] != measurement['qp']:
                raise ValueError('reconstructed V6 choices differ from already committed DEV choices')
            measurements.append({'qp': measurement['qp'], 'v2': CANDIDATES[base], 'v6': v6,
                                 'bpp': {o['name']: float(o['bpp']) for o in obs}})
        sources.append({**source, 'measurements': measurements})
    data = {'kind': 'v11_label_free_dev_input', 'stage': 'dev', 'provenance': context,
            'historical_cache_lock_sha256': lock_sha, 'historical_dev_tree_sha256': tree,
            'historical_v6_selection_sha256': cal.hash_bytes(cal.committed('configs/v7_mc3_dev_selection.json')),
            'sources': sources}
    write_json(REPO / INPUT, data)
    return {'sources': len(sources), 'input_sha256': sha256(REPO / INPUT)}


def matches_context(record: dict, context: dict) -> bool:
    return {k: v for k, v in record.items() if k != 'code_commit'} == {k: v for k, v in context.items() if k != 'code_commit'}


def load_input(plan: dict, context: dict) -> tuple[dict, str]:
    raw = cal.committed(INPUT)
    if cal.hash_bytes(raw) != cal.committed(INPUT.replace('.json', '.sha256')).decode().split()[0]:
        raise ValueError('DEV input hash mismatch')
    data = json.loads(raw)
    if data.get('kind') != 'v11_label_free_dev_input' or data.get('stage') != 'dev' or not matches_context(data['provenance'], context):
        raise ValueError('DEV input provenance changed')
    cal.git('merge-base', '--is-ancestor', data['provenance']['code_commit'], 'HEAD')
    if len(data['sources']) != 200:
        raise ValueError('DEV input incomplete')
    for row, expected in zip(data['sources'], plan['stages']['dev'], strict=True):
        if (set(row) != {'sequence_id', 'source_sha256', 'measurements'}
                or {k: row[k] for k in expected} != expected or len(row['measurements']) != 5):
            raise ValueError('DEV input source/schema changed')
        for item, qp in zip(row['measurements'], QPS, strict=True):
            if (set(item) != {'qp', 'v2', 'v6', 'bpp'} or item['qp'] != qp
                    or item['v2'] not in CANDIDATES or item['v6'] not in CANDIDATES
                    or set(item['bpp']) != set(CANDIDATES)
                    or any(not finite(v) or v <= 0 for v in item['bpp'].values())):
                raise ValueError('DEV input choice or rate changed')
    return data, cal.hash_bytes(raw)


def finite(v) -> bool:
    return type(v) in (int, float) and math.isfinite(v)


def validate_proxy(row: dict, source: dict) -> None:
    if (set(row) != {'sequence_id', 'source_sha256', 'measurements'} or row['sequence_id'] != source['sequence_id']
            or row['source_sha256'] != source['source_sha256'] or len(row['measurements']) != 5):
        raise ValueError('proxy source or schema changed')
    for item, fixed in zip(row['measurements'], source['measurements'], strict=True):
        if set(item) != {'qp', 'candidates'} or item['qp'] != fixed['qp'] or set(item['candidates']) != cal.measured_names(fixed):
            raise ValueError('proxy candidate/QP changed')
        for name, value in item['candidates'].items():
            if (set(value) != {'bpp', 'd112', 'coded_bytes', 'decoded_sha256', 'encode_decode_s'}
                    or not finite(value['bpp']) or abs(value['bpp'] - fixed['bpp'][name]) > 1e-9
                    or not finite(value['d112']) or not 0 <= value['d112'] <= 2
                    or type(value['coded_bytes']) is not int or value['coded_bytes'] <= 0
                    or abs(value['coded_bytes'] * 8 / (16 * 128 * 128) - value['bpp']) > 1e-9
                    or not re.fullmatch('[0-9a-f]{64}', value['decoded_sha256'])
                    or not finite(value['encode_decode_s']) or value['encode_decode_s'] < 0):
                raise ValueError('proxy rate, distance, count or hash invalid')


def make_selection(row: dict, source: dict, policy: dict) -> dict:
    validate_proxy(row, source)
    points = []
    for measured, fixed in zip(row['measurements'], source['measurements'], strict=True):
        proxy = {k: {f: v[f] for f in ('bpp', 'd112')} for k, v in measured['candidates'].items()}
        name, reason = choose(fixed['qp'], fixed, proxy, policy)
        choices = {'identity': 'identity128', 'area112': 'area112', 'v2': fixed['v2'], 'v6': fixed['v6'], 'v11': name}
        points.append({'qp': fixed['qp'], 'choices': choices, 'reason': reason,
                       'bpp': {arm: fixed['bpp'][n] for arm, n in choices.items()},
                       'proxy_candidates': measured['candidates']})
    return {'sequence_id': source['sequence_id'], 'source_sha256': source['source_sha256'], 'measurements': points}


def source_paths(root: Path, sources: list[dict]) -> dict:
    if not root.is_dir() or not ffmpeg_available():
        raise ValueError('source root/FFmpeg unavailable')
    paths = find_planned_videos(root, [s['sequence_id'] for s in sources])
    if any(sha256(paths[s['sequence_id']]) != s['source_sha256'] for s in sources):
        raise ValueError('source bytes mismatch before work')
    return paths


def versions() -> dict:
    return {'python': platform.python_version(), 'torch': torch.__version__, 'opencv': cv2.__version__,
            'numpy': np.__version__, 'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0]}


def proxy_shard(root: Path, shard: int, out: Path, data: dict, context: dict, input_sha: str) -> dict:
    if shard not in range(SHARDS) or out.exists():
        raise ValueError('invalid shard or existing output')
    sources = data['sources'][shard::SHARDS]
    paths = source_paths(root, sources)
    torch.manual_seed(SEED)
    torch.set_num_threads(2)
    out.mkdir(parents=True)
    codec = StandardCodec('h265', preset='medium', strict_decode=True)
    rows, trials = [], 0
    for i, source in enumerate(sources, 1):
        row, count = cal.measure_source(source, paths[source['sequence_id']], codec)
        validate_proxy(row, source)
        rows.append(row)
        trials += count
        print(f'[V11 DEV proxy] shard={shard} {i}/50 trials={trials}', flush=True)
    raw = out / 'shard_records.jsonl'
    raw.write_bytes(cal.rows_bytes(rows))
    write_json(out / 'manifest.json', {'kind': 'v11_dev_proxy_shard', 'provenance': context,
        'input_sha256': input_sha, 'shard': shard, 'shards': SHARDS, 'n': len(rows),
        'source_ids': [s['sequence_id'] for s in sources], 'records_sha256': sha256(raw),
        'trial_encode_decode_count': trials, 'device': 'cpu; no analyzer or labels', 'versions': versions()})
    return {'shard': shard, 'records': len(rows), 'trial_encode_decode_count': trials}


def load_bundles(folders: list[Path], kind: str, sources: list[dict], context: dict, binding: dict) -> tuple[list, list]:
    if len(folders) != SHARDS:
        raise ValueError('exactly four shard directories required')
    by_id, bundles, worker_commits = {}, {}, set()
    for folder in folders:
        meta_path, raw = folder / 'manifest.json', folder / 'shard_records.jsonl'
        meta = json.loads(meta_path.read_bytes())
        shard = meta.get('shard')
        if type(shard) is not int or shard not in range(SHARDS) or shard in bundles:
            raise ValueError('duplicate or invalid shard')
        assigned = sources[shard::SHARDS]
        if (meta.get('kind') != kind or meta.get('shards') != SHARDS or meta.get('n') != 50
                or not matches_context(meta.get('provenance', {}), context)
                or any(meta.get(k) != v for k, v in binding.items())
                or sha256(meta_path) != meta_path.with_suffix('.sha256').read_text().split()[0]
                or meta.get('records_sha256') != sha256(raw)
                or meta.get('source_ids') != [s['sequence_id'] for s in assigned]):
            raise ValueError('shard provenance, hash or partition mismatch')
        worker = meta['provenance']['code_commit']
        if not re.fullmatch('[0-9a-f]{40}', worker):
            raise ValueError('worker commit missing')
        cal.git('merge-base', '--is-ancestor', worker, 'HEAD')
        worker_commits.add(worker)
        rows = [json.loads(line) for line in raw.read_bytes().splitlines()]
        if len(rows) != 50:
            raise ValueError('shard records incomplete')
        trials = 0
        for row, source in zip(rows, assigned, strict=True):
            if kind == 'v11_dev_proxy_shard':
                validate_proxy(row, source)
                trials += sum(len(m['candidates']) for m in row['measurements'])
            else:
                validate_score(row, source)
                trials += sum(m['unique_streams'] for m in row['measurements'])
            if row['sequence_id'] in by_id:
                raise ValueError('duplicate source')
            by_id[row['sequence_id']] = row
        if meta.get('trial_encode_decode_count') != trials:
            raise ValueError('trial count inconsistent')
        bundles[shard] = {**meta, 'manifest_sha256': sha256(meta_path)}
    if len(worker_commits) != 1:
        raise ValueError('mixed worker commits')
    return [by_id[s['sequence_id']] for s in sources], [bundles[i] for i in range(SHARDS)]


def seal(folders: list[Path], data: dict, context: dict, input_sha: str) -> dict:
    rows, manifests = load_bundles(folders, 'v11_dev_proxy_shard', data['sources'], context, {'input_sha256': input_sha})
    sources = [make_selection(row, source, context['policy']) for row, source in zip(rows, data['sources'], strict=True)]
    artifact = {'kind': 'v11_globally_locked_dev_selection', 'provenance': context, 'n': len(sources),
                'input_sha256': input_sha, 'all_choices_before_any_analyzer_or_label': True,
                'proxy_shard_manifests': manifests, 'sources': sources}
    write_json(REPO / SELECTION, artifact)
    return {'sources': len(sources), 'selection_sha256': sha256(REPO / SELECTION), 'status': 'COMMIT_BEFORE_SCORING'}


def load_selection(data: dict, context: dict, input_sha: str) -> tuple[dict, str]:
    raw = cal.committed(SELECTION)
    artifact = json.loads(raw)
    if (cal.hash_bytes(raw) != cal.committed(SELECTION.replace('.json', '.sha256')).decode().split()[0]
            or artifact.get('kind') != 'v11_globally_locked_dev_selection'
            or artifact.get('n') != 200 or len(artifact.get('sources', [])) != 200
            or not matches_context(artifact.get('provenance', {}), context)
            or artifact.get('input_sha256') != input_sha or artifact.get('all_choices_before_any_analyzer_or_label') is not True):
        raise ValueError('global selection is uncommitted, changed or incomplete')
    for chosen, source in zip(artifact['sources'], data['sources'], strict=True):
        proxy_row = {'sequence_id': chosen['sequence_id'], 'source_sha256': chosen['source_sha256'],
                     'measurements': [{'qp': m['qp'], 'candidates': m['proxy_candidates']} for m in chosen['measurements']]}
        if make_selection(proxy_row, source, context['policy']) != chosen:
            raise ValueError('selection differs from frozen policy or source')
    return artifact, cal.hash_bytes(raw)


def score_source(source: dict, path: Path, analyzers: dict, codec, label: int) -> dict:
    # No policy selection occurs here: consume the committed global manifest.
    from ops.paper_heldout_mc3 import timed_inference
    if sha256(path) != source['source_sha256']:
        raise ValueError('source bytes changed')
    variants = make_candidates(read_clip(path))
    points = []
    for fixed in source['measurements']:
        streams = {}
        for name in sorted(set(fixed['choices'].values())):
            candidate = variants[name]
            start = time.perf_counter()
            decoded, native_bpp = codec._encode_decode_clip(candidate, qp=fixed['qp'])
            elapsed = time.perf_counter() - start
            bpp = normalized_bpp(native_bpp, *candidate.shape[1:3])
            reference = next(fixed['bpp'][a] for a in ARMS if fixed['choices'][a] == name)
            decoded_sha = cal.hash_bytes(decoded.tobytes())
            if (abs(bpp - reference) > 1e-9 or name in fixed['proxy_candidates']
                    and decoded_sha != fixed['proxy_candidates'][name]['decoded_sha256']):
                raise ValueError('score stream differs from globally locked proxy stream')
            predictions = {}
            for model, analyzer in analyzers.items():
                pred, seconds = timed_inference(analyzer, decoded)
                predictions[model] = {'predicted_class_index': pred, 'correct': pred == label, 'inference_s': seconds}
            streams[name] = {'name': name, 'bpp': bpp, 'coded_bytes': round(bpp * 16 * 128 * 128 / 8),
                             'decoded_sha256': decoded_sha, 'encode_decode_s': elapsed, 'analyzers': predictions}
        points.append({'qp': fixed['qp'], 'unique_streams': len(streams),
                       'arms': {a: streams[fixed['choices'][a]] for a in ARMS}})
    return {'sequence_id': source['sequence_id'], 'source_sha256': source['source_sha256'], 'label': label, 'measurements': points}


def validate_score(row: dict, source: dict) -> None:
    from src.tasks.action_recognition import _canon, kinetics_category_index
    label = kinetics_category_index(MODELS[0]).get(_canon(source['sequence_id'].split('/')[0]))
    if (set(row) != {'sequence_id', 'source_sha256', 'label', 'measurements'}
            or row['sequence_id'] != source['sequence_id'] or row['source_sha256'] != source['source_sha256']
            or type(row['label']) is not int or row['label'] != label or len(row['measurements']) != 5):
        raise ValueError('score source/label/schema mismatch')
    for item, fixed in zip(row['measurements'], source['measurements'], strict=True):
        if (set(item) != {'qp', 'unique_streams', 'arms'} or item['qp'] != fixed['qp']
                or set(item['arms']) != set(ARMS) or item['unique_streams'] != len(set(fixed['choices'].values()))):
            raise ValueError('score QP/arm/reuse mismatch')
        seen = {}
        for arm in ARMS:
            value = item['arms'][arm]
            name = fixed['choices'][arm]
            if (set(value) != {'name', 'bpp', 'coded_bytes', 'decoded_sha256', 'encode_decode_s', 'analyzers'}
                    or value['name'] != name or not finite(value['bpp']) or abs(value['bpp'] - fixed['bpp'][arm]) > 1e-9
                    or type(value['coded_bytes']) is not int or value['coded_bytes'] <= 0
                    or abs(value['coded_bytes'] * 8 / (16 * 128 * 128) - value['bpp']) > 1e-9
                    or not re.fullmatch('[0-9a-f]{64}', value['decoded_sha256'])
                    or not finite(value['encode_decode_s']) or value['encode_decode_s'] < 0
                    or set(value['analyzers']) != set(MODELS)):
                raise ValueError('score stream invalid')
            if name in fixed['proxy_candidates'] and value['decoded_sha256'] != fixed['proxy_candidates'][name]['decoded_sha256']:
                raise ValueError('score decoded pixels differ from proxy phase')
            if name in seen and seen[name] != value:
                raise ValueError('shared stream has inconsistent score')
            seen[name] = value
            for prediction in value['analyzers'].values():
                if (set(prediction) != {'predicted_class_index', 'correct', 'inference_s'}
                        or type(prediction['predicted_class_index']) is not int or not 0 <= prediction['predicted_class_index'] < 400
                        or type(prediction['correct']) is not bool or prediction['correct'] != (prediction['predicted_class_index'] == label)
                        or not finite(prediction['inference_s']) or prediction['inference_s'] < 0):
                    raise ValueError('analyzer score invalid')


def score_shard(root: Path, shard: int, out: Path, selected: dict, context: dict, input_sha: str, selection_sha: str) -> dict:
    # load_selection was completed for ALL 200 sources before importing label helpers or constructing any analyzer.
    if shard not in range(SHARDS) or out.exists():
        raise ValueError('invalid shard or existing output')
    sources = selected['sources'][shard::SHARDS]
    paths = source_paths(root, sources)
    from src.tasks.action_recognition import ActionRecognitionAnalyzer, _canon, kinetics_categories, kinetics_category_index
    import torchvision
    if any(kinetics_categories(m) != kinetics_categories(MODELS[0]) for m in MODELS):
        raise ValueError('analyzer category order mismatch')
    labels = kinetics_category_index(MODELS[0])
    torch.manual_seed(SEED)
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    analyzers = {m: ActionRecognitionAnalyzer(m, clip_size=112).freeze().to(device) for m in MODELS}
    weights = {}
    for model, analyzer in analyzers.items():
        chunks = []
        for key, tensor in sorted(analyzer.net.state_dict().items()):
            array = tensor.detach().cpu().numpy()
            chunks.append(f'{key}:{array.dtype}:{array.shape}:'.encode() + array.tobytes())
        weights[model] = cal.hash_bytes(b''.join(chunks))
    out.mkdir(parents=True)
    codec = StandardCodec('h265', preset='medium', strict_decode=True)
    rows = []
    raw = out / 'shard_records.jsonl'
    with raw.open('wb') as stream:
        for i, source in enumerate(sources, 1):
            label = labels.get(_canon(source['sequence_id'].split('/')[0]))
            if label is None:
                raise ValueError('unmapped Kinetics class')
            row = score_source(source, paths[source['sequence_id']], analyzers, codec, label)
            validate_score(row, source)
            stream.write(cal.rows_bytes([row]))
            stream.flush()
            rows.append(row)
            print(f'[V11 DEV score] shard={shard} {i}/50', flush=True)
    write_json(out / 'manifest.json', {'kind': 'v11_dev_score_shard', 'provenance': context,
        'input_sha256': input_sha, 'selection_sha256': selection_sha, 'shard': shard, 'shards': SHARDS,
        'n': len(rows), 'source_ids': [s['sequence_id'] for s in sources], 'records_sha256': sha256(raw),
        'trial_encode_decode_count': sum(m['unique_streams'] for r in rows for m in r['measurements']),
        'analyzers': list(MODELS), 'analyzer_weights_sha256': weights, 'device': str(device),
        'versions': {**versions(), 'torchvision': torchvision.__version__},
        'timing_scope': 'evaluation only; not full six-candidate selector runtime'})
    return {'shard': shard, 'records': len(rows)}


def merge(folders: list[Path], out: Path, selected: dict, context: dict, input_sha: str, selection_sha: str) -> dict:
    if out.exists() or out.with_suffix('.sha256').exists():
        raise ValueError('fresh merge output required')
    rows, manifests = load_bundles(folders, 'v11_dev_score_shard', selected['sources'], context,
                                 {'input_sha256': input_sha, 'selection_sha256': selection_sha})
    weights = manifests[0].get('analyzer_weights_sha256', {})
    if (set(weights) != set(MODELS) or any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) for v in weights.values())
            or any(m.get('analyzers') != list(MODELS) or m.get('analyzer_weights_sha256') != weights for m in manifests)):
        raise ValueError('shards used different analyzers/weights')
    resamples = np.random.default_rng(SEED).integers(0, len(rows), size=(DRAWS, len(rows)))
    comparisons = {}
    for name, anchor, trial in (('V2-C_vs_identity', 'identity', 'v2'), ('V6_vs_identity', 'identity', 'v6'),
                               ('area112_vs_identity', 'identity', 'area112'), ('V11_vs_identity', 'identity', 'v11'),
                               ('V11_vs_V2-C', 'v2', 'v11'), ('V11_vs_V6', 'v6', 'v11'), ('V11_vs_area112', 'area112', 'v11')):
        comparisons[name] = {m: summarize(rows, anchor, trial, m, resamples) for m in MODELS}
    main = comparisons['V11_vs_identity']
    original = all(finite(main[m]['metrics']['bd_rate_top1_pct']) and main[m]['metrics']['bd_rate_top1_pct'] < -15
                   and finite(main[m]['metrics']['bd_accuracy_top1_pp']) and main[m]['metrics']['bd_accuracy_top1_pp'] > 0 for m in MODELS[:2])
    report = {'kind': 'v11_dev_result', 'provenance': context, 'n': len(rows), 'input_sha256': input_sha,
              'selection_sha256': selection_sha, 'sources': [{k: s[k] for k in ('sequence_id', 'source_sha256')} for s in selected['sources']],
              'shard_manifests': manifests, 'comparisons': comparisons, **engineering_gate(main),
              'original_primary_point_gate_on_reused_dev': original,
              'original_gate': 'NOT CONFIRMATORY: reused DEV; threshold remains -15%', 'holdout': 'CHƯA ĐO'}
    write_json(out, report)
    return {'result_sha256': sha256(out), 'go_no_go': report['go_no_go'], 'checks': report['checks']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    prepare = subs.add_parser('prepare')
    prepare.add_argument('--cache-root', type=Path, required=True)
    preflight = subs.add_parser('preflight')
    preflight.add_argument('--phase', choices=('proxy', 'score'), required=True)
    for command in ('proxy-shard', 'score-shard'):
        p = subs.add_parser(command)
        p.add_argument('--source-root', type=Path, required=True)
        p.add_argument('--shard', type=int, choices=range(SHARDS), required=True)
        p.add_argument('--out-dir', type=Path, required=True)
    for command in ('seal', 'merge'):
        p = subs.add_parser(command)
        p.add_argument('--shard-dir', type=Path, action='append', required=True)
        if command == 'merge':
            p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    plan, context = protocol()
    if args.command == 'prepare':
        result = prepare_input(args.cache_root, plan, context)
    else:
        data, input_sha = load_input(plan, context)
        if args.command in ('score-shard', 'merge') or args.command == 'preflight' and args.phase == 'score':
            selected, selection_sha = load_selection(data, context, input_sha)
        if args.command == 'preflight':
            result = {'phase': args.phase, 'sources': len(data['sources']), 'input_sha256': input_sha, 'code_commit': context['code_commit']}
        elif args.command == 'proxy-shard':
            result = proxy_shard(args.source_root, args.shard, args.out_dir, data, context, input_sha)
        elif args.command == 'seal':
            result = seal(args.shard_dir, data, context, input_sha)
        elif args.command == 'score-shard':
            result = score_shard(args.source_root, args.shard, args.out_dir, selected, context, input_sha, selection_sha)
        else:
            result = merge(args.shard_dir, args.out, selected, context, input_sha, selection_sha)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
