from copy import deepcopy
import json

import numpy as np
import pytest

from ops import v11_spatial_dev as dev
from ops.push_v11_spatial_dev import payload
from ops.v11_spatial_dev import (ARMS, MODELS, QPS, label_free_object, make_selection,
                                validate_proxy, validate_score, engineering_gate)
from ops.v8_motion_pilot import summarize
from src.tasks.action_recognition import kinetics_category_index


def fixture():
    source = {'sequence_id': 'abseiling/example.mp4', 'source_sha256': 'a' * 64,
              'measurements': [{'qp': q, 'v2': 'identity128', 'v6': 'area112',
                                'bpp': {'identity128': .125, 'area112': .12}} for q in QPS]}
    rows = {'sequence_id': source['sequence_id'], 'source_sha256': source['source_sha256'],
            'measurements': [{'qp': q, 'candidates': {
                n: {'bpp': rate, 'd112': dist, 'coded_bytes': round(rate * 32768),
                    'decoded_sha256': 'b' * 64, 'encode_decode_s': 0.1}
                for n, rate, dist in [('identity128', .125, .1), ('area112', .12, .3)]}} for q in QPS]}
    # Fixed coded-byte denominator requires exactly representable bpp.
    for row, fixed in zip(rows['measurements'], source['measurements']):
        for name, value in row['candidates'].items():
            value['bpp'] = value['coded_bytes'] / 32768
            fixed['bpp'][name] = value['bpp']
    return source, rows


def test_proxy_selection_is_label_free_and_uses_frozen_rule():
    source, row = fixture()
    selected = make_selection(row, source, {'tau': 0.0, 'slack': .05, 'qp_mode': 'all'})
    assert all(m['choices']['v11'] == 'identity128' for m in selected['measurements'])
    assert all(m['reason'] == 'v2_spatial_rescue' for m in selected['measurements'])
    changed = deepcopy(row)
    changed['label'] = 5
    with pytest.raises(ValueError):
        make_selection(changed, source, {'tau': 0.0, 'slack': .05, 'qp_mode': 'all'})
    changed = deepcopy(row)
    changed['measurements'][0]['candidates']['area112']['bpp'] += .001
    with pytest.raises(ValueError):
        validate_proxy(changed, source)


def test_proxy_rejects_missing_qp_and_nonfinite_distance():
    source, row = fixture()
    changed = deepcopy(row)
    changed['measurements'].pop()
    with pytest.raises(ValueError):
        validate_proxy(changed, source)
    row['measurements'][0]['candidates']['area112']['d112'] = float('nan')
    with pytest.raises(ValueError):
        validate_proxy(row, source)


def test_cache_loader_drops_outcomes_at_parse_boundary():
    result = json.loads('{"label":7,"measurements":[{"correct":true,"cross_correct":false,"signals":{"margin":0.2}}]}', object_hook=label_free_object)
    assert result == {'measurements': [{'signals': {'margin': .2}}]}


def test_score_rejects_changed_choices_predictions_and_shared_streams():
    source, proxy = fixture()
    selected = make_selection(proxy, source, {'tau': 0.0, 'slack': .05, 'qp_mode': 'all'})
    label = kinetics_category_index(MODELS[0])['abseiling']
    measurements = []
    for m in selected['measurements']:
        values = {}
        for arm in ARMS:
            name = m['choices'][arm]
            values[arm] = {'name': name, 'bpp': m['bpp'][arm], 'coded_bytes': round(m['bpp'][arm]*32768),
                           'decoded_sha256': 'b'*64, 'encode_decode_s': .1,
                           'analyzers': {model: {'predicted_class_index': label, 'correct': True, 'inference_s': .1} for model in MODELS}}
        measurements.append({'qp': m['qp'], 'unique_streams': 2, 'arms': values})
    row = {'sequence_id': source['sequence_id'], 'source_sha256': source['source_sha256'], 'label': label, 'measurements': measurements}
    validate_score(row, selected)
    for field, value in [('correct', False), ('predicted_class_index', 401)]:
        changed = deepcopy(row)
        changed['measurements'][0]['arms']['v11']['analyzers']['mc3_18'][field] = value
        with pytest.raises(ValueError):
            validate_score(changed, selected)
    changed = deepcopy(row)
    changed['measurements'][0]['arms']['v11']['decoded_sha256'] = 'c'*64
    with pytest.raises(ValueError):
        validate_score(changed, selected)


def test_paired_bootstrap_operates_on_whole_sources():
    rows = []
    for i in range(20):
        measurements = []
        for j, qp in enumerate(QPS):
            good = i < 18-4*j
            make = lambda rate: {'bpp': rate, 'analyzers': {'mc3_18': {'correct': good}}}
            measurements.append({'qp': qp, 'arms': {'identity': make(.25-.04*j), 'v11': make(.9*(.25-.04*j))}})
        rows.append({'measurements': measurements})
    indices = np.random.default_rng(20261008).integers(0,20,(100,20))
    result = summarize(rows, 'identity', 'v11', 'mc3_18', indices)
    assert result['metrics']['bd_rate_top1_pct'] == pytest.approx(-10)
    assert result['bootstrap']['bd_rate_top1_pct']['requested_draws'] == 100
    assert result['bootstrap']['bd_rate_top1_pct']['ci95'] == pytest.approx([-10,-10])


def test_gate_retains_strict_targets_and_valid_draw_requirement():
    metrics = {'bd_rate_top1_pct': -11., 'bd_accuracy_top1_pp': .1, 'min_same_qp_top1_gap_pp': -1.}
    intervals = {k: {'valid_draws': 2000, 'requested_draws': 2000, 'ci95': [-2., .5]} for k in ('bd_rate_top1_pct','bd_accuracy_top1_pp')}
    main = {m: {'metrics': deepcopy(metrics), 'bootstrap': deepcopy(intervals)} for m in MODELS}
    main['mc3_18']['metrics']['bd_rate_top1_pct'] = -.1
    assert engineering_gate(main)['go_no_go']
    main['mc3_18']['bootstrap']['bd_rate_top1_pct']['ci95'][1] = 1.01
    assert not engineering_gate(main)['go_no_go']
    main['mc3_18']['bootstrap']['bd_rate_top1_pct']['ci95'][1] = 1.
    main['r3d_18']['bootstrap']['bd_accuracy_top1_pp']['valid_draws'] = 1899
    assert not engineering_gate(main)['go_no_go']


def test_private_payload_distinguishes_no_analyzer_proxy_and_scoring():
    for phase in ('proxy','score'):
        book, meta = payload('a'*40,'shungg05',f'v11-dev-{phase}-s0',0,phase)
        shell = ''.join(book['cells'][0]['source'])
        assert meta['is_private'] and meta['enable_gpu'] == (phase == 'score')
        assert f'PHASE="{phase}"' in shell and 'preflight --phase' in shell
        assert 'a'*40 in shell and '__REF__' not in shell
    with pytest.raises(ValueError):
        payload('a'*40,'shungg05','v11-dev',4,'score')


def test_cli_scoring_cannot_start_before_global_selection(monkeypatch, tmp_path):
    monkeypatch.setattr('sys.argv', ['v11', 'score-shard', '--source-root', str(tmp_path), '--shard', '0', '--out-dir', str(tmp_path/'out')])
    monkeypatch.setattr(dev, 'protocol', lambda: ({}, {}))
    monkeypatch.setattr(dev, 'load_input', lambda *args: ({'sources': []}, 'a'*64))
    calls = []
    def missing_selection(*args):
        calls.append('global selection checked')
        raise ValueError('selection not committed')
    monkeypatch.setattr(dev, 'load_selection', missing_selection)
    monkeypatch.setattr(dev, 'score_shard', lambda *args: pytest.fail('scoring started before global freeze'))
    with pytest.raises(ValueError, match='selection not committed'):
        dev.main()
    assert calls == ['global selection checked']
