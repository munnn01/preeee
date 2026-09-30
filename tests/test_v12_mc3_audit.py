from copy import deepcopy
import json
import numpy as np
import pytest
from research.v12_mc3_audit import study
from research.v12_mc3_audit.push import payload

def fixture_source(i=0):
    clip=np.zeros((16,128,128,3),dtype=np.uint8)
    expected={'bpp':.5,'coded_bytes':16384,'decoded_sha256':study.sha(clip.tobytes())}
    arms={'identity':'identity128','v6':'identity128','area112':'area112','v12a':'identity128','v12b':'identity128'}
    source={'sequence_id':f'drawing/source{i}.mp4','source_sha256':f'{i+1:064x}',
        'measurements':[{'qp':q,'arms':dict(arms),'streams':{n:dict(expected) for n in set(arms.values())}} for q in study.QPS]}
    return source,clip

def fixture_index():
    sources=[fixture_source(i)[0] for i in range(200)]
    data={'kind':'v12_frozen_mc3_CAL_selection','scope':'diagnostic','parent_freezes':{},'n':200,'qps':list(study.QPS),
        'shards':4,'sources':sources}
    cfg={'parent_freezes':{},'source_fingerprint':study.fingerprint([s['sequence_id'] for s in sources])}
    return data,cfg

@pytest.mark.parametrize('field',['correct','label','prediction'])
def test_frozen_index_rejects_outcome_fields(field):
    data,cfg=fixture_index()
    study.validate_input(data,cfg)
    data['sources'][0][field]=1
    with pytest.raises(ValueError): study.validate_input(data,cfg)

def test_frozen_cohort_and_high_qp_choices_cannot_change():
    data,cfg=fixture_index()
    data['sources'][1]['source_sha256']=data['sources'][0]['source_sha256']
    with pytest.raises(ValueError): study.validate_input(data,cfg)
    data,cfg=fixture_index()
    data['sources'][0]['measurements'][-1]['arms']['v12a']='area112'
    with pytest.raises(ValueError): study.validate_input(data,cfg)

def fake_evaluation(monkeypatch,source,clip,damage=None):
    monkeypatch.setattr(study,'make_candidates',lambda x:{n:clip for n in ('identity128','area112')})
    class Codec:
        calls=0
        def _encode_decode_clip(self,candidate,qp):
            self.calls+=1
            return candidate,(.75 if damage=='bpp' else .5)
    calls=[]
    def predict(decoded):
        calls.append(decoded)
        return 10,.01
    codec=Codec()
    if damage=='pixels': source['measurements'][0]['streams']['identity128']['decoded_sha256']='b'*64
    return codec,predict,calls

def test_duplicate_arms_share_one_actual_encode_and_inference(monkeypatch):
    source,clip=fixture_source()
    codec,predict,calls=fake_evaluation(monkeypatch,source,clip)
    row=study.evaluate_source(source,clip,codec,predict,10)
    assert codec.calls==len(calls)==10 # two unique streams x five QPs, not five arms x five QPs
    boot=study.bootstrap_rows([row])[0]
    for point in boot['measurements']:
        assert point['arms']['identity']==point['arms']['v6']==point['arms']['v12a']==point['arms']['v12b']
        assert point['arms']['identity']['analyzers']['mc3_18']['correct']

@pytest.mark.parametrize('damage',['pixels','bpp'])
def test_codec_mismatch_stops_before_any_model_inference(monkeypatch,damage):
    source,clip=fixture_source()
    codec,predict,calls=fake_evaluation(monkeypatch,source,clip,damage)
    with pytest.raises(ValueError): study.evaluate_source(source,clip,codec,predict,10)
    assert calls==[]

def test_score_truth_and_stream_names_are_checked(monkeypatch):
    source,clip=fixture_source()
    codec,predict,_=fake_evaluation(monkeypatch,source,clip)
    row=study.evaluate_source(source,clip,codec,predict,10)
    for damage in ('score','choice'):
        bad=deepcopy(row)
        if damage=='score': bad['measurements'][0]['streams']['identity128']['correct']=False
        else: bad['measurements'][0]['arms']['v12a']='area112'
        with pytest.raises(ValueError): study.validate_record(bad,source,10)

def test_mc3_gate_keeps_original_limits_and_marks_insufficient_draws():
    entry={'metrics':{'bd_rate_top1_pct':-1,'bd_accuracy_top1_pp':1,'min_same_qp_top1_gap_pp':-1},
        'bootstrap':{k:{'valid_draws':1900,'requested_draws':2000,'ci95':[-2,1]} for k in ('bd_rate_top1_pct','bd_accuracy_top1_pp')}}
    assert study.component_gate(entry)=='PASS_ON_REUSED_CAL_ONLY'
    bad=deepcopy(entry)
    bad['metrics']['bd_rate_top1_pct']=0
    assert study.component_gate(bad)=='FAIL_ON_REUSED_CAL'
    bad=deepcopy(entry)
    bad['bootstrap']['bd_rate_top1_pct']['ci95'][1]=1.01
    assert study.component_gate(bad)=='FAIL_ON_REUSED_CAL'
    entry['bootstrap']['bd_rate_top1_pct']['valid_draws']=1899
    assert study.component_gate(entry)=='INCONCLUSIVE_INSUFFICIENT_DRAWS'

def test_private_gpu_notebook_has_full_pins_and_no_selector_command():
    book,meta=payload('a'*40,'b'*40,'example1','mc3-v12-cal-s0',0)
    shell=''.join(book['cells'][0]['source'])
    assert meta['is_private'] and meta['enable_gpu'] and meta['dataset_sources']==['qktttttttttt/kineticscleaned']
    assert 'a'*40 in shell and 'b'*40 in shell and 'research.v12_mc3_audit.study' in shell
    assert 'calibrate' not in shell and 'holdout' not in shell
