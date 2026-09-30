# V11 H.265 analyzer-grid CAL runbook

The [locked protocol](PREREGISTRATION_V11_112_RESIDUAL.md) is commit `00951bd52efeb3c64feb62254cef2aa484431e60`. V11 CAL, DEV, `mc3_18` and holdout are **CHƯA ĐO** until validated artifacts say otherwise. The source plan and V2/V6 choices are reused development inputs; this run cannot establish independent confirmation.

The worker uses the 200 committed CAL source IDs and byte hashes, four shards of 50, H.265 medium and five QPs. It re-encodes only the unique identity/V2/V6 choices per source–QP. `ops.v11_spatial_cal` refuses uncommitted changes to code, changed source/input hashes and a repeated calibration result. It records distance at the analyzers' 112-pixel input grid before reading any classifier correctness.

From the repository root, with `D:\STUDY\AI\envs\ten_env\python.exe` as `$py`, the pinned public code commit as `$revision`, and the locked preregistration commit as `$prereg`:

```powershell
& $py -m ops.v11_spatial_cal --prereg-commit $prereg preflight
$accounts = @('shungg05','dieulinhh','huolgggnuyen','baooo25r')
for ($i=0; $i -lt 4; $i++) {
    & $py -m ops.push_v11_spatial_cal --commit $revision --prereg-commit $prereg --account $accounts[$i] --slug "v11-spatial-cal-s$i-$($revision.Substring(0,7))" --shard $i
}
```

The four Kaggle notebooks are private CPU jobs using `qktttttttttt/kineticscleaned`. Each clones exactly `$revision` from `munnn01/preeee`. Download `v11_cal_shard0.tgz` through `v11_cal_shard3.tgz`, verify member paths and types before extraction, then pass the extracted `outputs/v11_spatial_cal/shard0` through `shard3` directories to:

```powershell
& $py -m ops.v11_spatial_cal --prereg-commit $prereg calibrate --cache-root 'D:\STUDY\LAB\proxy_v3\_paper_v2_audit\v7_dev_stage\cache\dual_codec_search_v2\h265' --shard-dir $cal0 --shard-dir $cal1 --shard-dir $cal2 --shard-dir $cal3
```

The calibration command validates every raw record against pinned rates and hashes, joins only historical primary correctness, evaluates all 36 locked policies and writes `configs/v11_spatial/frozen_calibration.json` with a SHA-256 sidecar. Commit complete results, including negative outcomes. If `selected_policy` is null, stop. Only after a feasible policy is frozen may a separately audited DEV worker be completed and used under the same preregistered rules. `mc3_18` is absent from CAL selection; a future holdout needs another preregistration.
