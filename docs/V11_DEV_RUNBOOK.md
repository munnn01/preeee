# V11 DEV: global selection freeze before scoring

The [V11 preregistration](PREREGISTRATION_V11_112_RESIDUAL.md) is unchanged. CAL policy `tau=0, slack=0.05, qp_mode=all` and the full CAL grid were frozen at commit `49fb15f6de86f09c6c0a845098cbbf199c405c03`, result SHA-256 `280c926a65458a00b192ed1cd0a44e6b341ac6a4f049c96852d5b0e15a410a0e`. DEV uses exactly the 200 previously used development sources in the locked source plan, fingerprint `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`. This study cannot establish fresh holdout confirmation.

## Two required phases

1. **Proxy:** four CPU notebooks, 50 sources each, measure the unique identity/V2-C/V6 streams at all five QPs. No analyzer is constructed and no label/correctness is used. Local input preparation reconstructs the already frozen V2/V6 decisions from the hash-locked historical cache, discards outcome fields at the parsing boundary, predicts with fixed V6 models, and verifies V6 choices against their already committed DEV manifest. It does not fit or tune anything.
2. **Global freeze:** download all four original proxy archives, check paths/types before extraction, validate source/record/manifest/input/code hashes and pinned bitrate, then `seal` all **200×5 choices**. Commit the complete selection JSON and sidecar before any scoring notebook can be published. Missing or changed sources stop the run; no replacements.
3. **Score:** four GPU notebooks read only the committed global selection and evaluate identity, area112, V2-C, V6, V11 with frozen `r2plus1d_18`, `r3d_18`, `mc3_18`. Shared streams are encoded/scored once per source-QP. Proxy streams must reproduce both pinned bpp and decoded-pixel SHA-256. Record model state hashes, predictions, ground truth, all trial counts and environment. No selection uses these scores.
4. **Merge:** merge all source records first, build complete five-QP curves and calculate direct comparisons. Reuse the unchanged metric/bootstrap implementation from `ops.v8_motion_pilot.summarize`; all comparisons and analyzers use the same **2,000 whole-source draws**, numpy `default_rng(20261008)`. No averaging of shard BD-rate.

**DEV scoring is complete and validated: NO-GO.** [Final report](RESULTS_V11_DEV.md) and [result/audit package](../results/v11_spatial_dev/README.md) bind the four original scoring archives. MC3 fails both the CI upper and same-QP guard; stop before new holdout. The original proxy phase itself contains no analyzer outcome. Timing is evaluation-only; full six-candidate selector overhead and V11 new holdout remain CHƯA ĐO. Frozen policy, global choices, original gate and preregistration are unchanged.

## Commands

Use the local environment `D:\STUDY\AI\envs\ten_env\python.exe` as `$py`. Commit implementation/tests before preparing input:

```powershell
& $py -m ops.v11_spatial_dev prepare --cache-root 'D:\STUDY\LAB\proxy_v3\_paper_v2_audit\v7_dev_stage\cache\dual_codec_search_v2\h265'
```

Commit `configs/v11_spatial/dev_input.json` and `.sha256`, publish that commit, set its full SHA as `$revision`, then:

```powershell
& $py -m ops.v11_spatial_dev preflight --phase proxy
$accounts = @('shungg05','dieulinhh','huolgggnuyen','baooo25r')
for ($i=0; $i -lt 4; $i++) {
    & $py -m ops.push_v11_spatial_dev --commit $revision --phase proxy --account $accounts[$i] --slug "v11-dev-proxy-s$i-$($revision.Substring(0,7))" --shard $i
}
```

After verified extraction of `v11_dev_proxy_shard0.tgz` through `3.tgz`:

```powershell
& $py -m ops.v11_spatial_dev seal --shard-dir $proxy0 --shard-dir $proxy1 --shard-dir $proxy2 --shard-dir $proxy3
```

Commit `configs/v11_spatial/dev_selection.json` and `.sha256` together with the raw proxy archive package. Publish the commit and use its full SHA as `$revision`. Only then:

```powershell
& $py -m ops.v11_spatial_dev preflight --phase score
for ($i=0; $i -lt 4; $i++) {
    & $py -m ops.push_v11_spatial_dev --commit $revision --phase score --account $accounts[$i] --slug "v11-dev-score-s$i-$($revision.Substring(0,7))" --shard $i
}
```

After verified extraction of all score archives, merge once into a fresh output:

```powershell
& $py -m ops.v11_spatial_dev merge --shard-dir $score0 --shard-dir $score1 --shard-dir $score2 --shard-dir $score3 --out results/v11_spatial_dev/h265_result.json
```

The DEV gate is unchanged: both primary BD-rates <−10%; mc3 BD-rate <0 with CI upper ≤+1%; all BD-accuracies >0 and all worst same-QP gaps ≥−1.00 pp; at least 1,900 valid draws for each analyzer's BD-rate and BD-accuracy. The original two-primary <−15% point gate is reported descriptively on reused DEV. No TEST or holdout command exists here; fresh confirmation requires a separate preregistration.

Every JSON has SHA-256 sidecar and provenance for code/preregistration/calibration/plan/input, source fingerprint, seed and bootstrap unit/count. The Kaggle notebooks are private, revision pinned, and use `qktttttttttt/kineticscleaned`. Keep complete negative outcomes and technical failures; never overwrite the CAL freeze or a DEV selection/result.
