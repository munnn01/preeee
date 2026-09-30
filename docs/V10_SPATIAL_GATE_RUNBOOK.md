# V10 execution runbook

Current state: draft protocol; no V10 CAL proxy extraction, selection, DEV assessment or holdout has run. The runner rejects the current `PREREGISTRATION_LOCKED: false` document. The historical CAL audit uses already measured V2 cache values and is not a V10 trial. Preserve existing artifacts and use new output folders.

## 1. Review and lock before measurements

Review [design](V10_SPATIAL_GATE_DESIGN.md), [draft protocol](PREREGISTRATION_V10_SPATIAL_GATE.md), and `configs/v10_spatial_plan.json`. After approval, change only the explicit lock flag to true and commit the protocol, source plan and completed implementation. Keep this full 40-character commit as PREREG. The plan SHA is a Git-blob hash, allowing only Git CRLF differences in a checkout; do not manually reformat JSON.

In PowerShell, set `$py` to `D:\STUDY\AI\envs\ten_env\python.exe`, `$prereg` to the approved protocol commit, and `$cache` to the audited cache root ending in `dual_codec_search_v2\h265`. The currently available local root is `D:\STUDY\LAB\proxy_v3\_paper_v2_audit\v7_dev_stage\cache\dual_codec_search_v2\h265`. Run from `D:\STUDY\LAB\pre_processor`.

```powershell
& $py -m ops.v10_spatial_gate --prereg-commit $prereg preflight
& $py -m ops.v10_spatial_gate --prereg-commit $prereg prepare --stage calibration --cache-root $cache
git add -- configs/v10_spatial/calibration_input.json configs/v10_spatial/calibration_input.sha256
git commit -m "Freeze V10 CAL input choices and measured byte references"
```

The preparation loads only historical CAL correctness and the fixed V6 artifacts. It serializes no labels or correctness: only IDs, video hashes, QPs, rates, frozen V2/V6 choices and provenance. Publish the exact input commit to the configured repository only with the needed authorization before a Kaggle notebook clones it.

## 2. Four CAL proxy shards

Set `$revision` to the full HEAD after committing CAL inputs. The four submissions run independently on Kaggle; each handles 50 unique sources, all six candidates and all five QPs. CAL uses CPU and constructs no analyzer. The existing local account pool supplies credentials; do not place tokens in command lines or repository files.

```powershell
$accounts = @('shungg05','dieulinhh','huolgggnuyen','baooo25r')
for ($i=0; $i -lt 4; $i++) {
    & $py -m ops.push_v10_spatial_gate --commit $revision --prereg-commit $prereg --account $accounts[$i] --slug "v10-spatial-cal-s$i-$($revision.Substring(0,7))" --stage calibration --shard $i
}
```

Add `--write-only` to generate notebook/metadata files without submitting. Inspect the private metadata and pinned commits. Never submit a new version over a currently running notebook; the push helper checks activity.

Download only `v10_calibration_shard0.tgz` through `v10_calibration_shard3.tgz` and the logs. Validate tar member paths and types before extracting. Expected roots are `outputs/v10_spatial_gate/calibration/shard0` through `shard3`. A completed Kaggle status is insufficient: all manifest and record validations must pass. Keep archive SHA-256 values in the result inventory.

```powershell
& $py -m ops.v10_spatial_gate --prereg-commit $prereg calibrate --cache-root $cache --shard-dir $cal0 --shard-dir $cal1 --shard-dir $cal2 --shard-dir $cal3
```

This writes `configs/v10_spatial/frozen_calibration.json` and its SHA-256 file. It reports all 81 policies. If selected_policy is null or status is NO_GO_STOP_BEFORE_DEV, stop; no fallback policy is promoted. Otherwise review the locked selection procedure, then commit these two artifacts. Do not pick a runner-up by hand or edit thresholds after results.

## 3. Frozen DEV assessment

```powershell
git add -- configs/v10_spatial/frozen_calibration.json configs/v10_spatial/frozen_calibration.sha256
git commit -m "Freeze V10 policy selected on CAL before DEV preparation"
& $py -m ops.v10_spatial_gate --prereg-commit $prereg prepare --stage dev --cache-root $cache
git add -- configs/v10_spatial/dev_input.json configs/v10_spatial/dev_input.sha256
git commit -m "Freeze V10 DEV inputs under selected CAL policy"
```

Set `$revision` to the new full HEAD and make it available to the Kaggle notebooks after publication authorization. Submit four jobs with the same loop, `--stage dev` and slugs `v10-spatial-dev-s$i-<shortcommit>`. DEV uses GPU for the three analyzers. Each shard first persists `proxy_records.jsonl` containing all decisions, then constructs analyzers and writes scored `shard_records.jsonl`. Temporary reconstructed RGB arrays are kept outside the artifact directory and are not archived. Same-stream arms reuse the same prediction.

Download/extract the four `v10_dev_shard*.tgz` archives. Use a fresh result path:

```powershell
& $py -m ops.v10_spatial_gate --prereg-commit $prereg merge --shard-dir $dev0 --shard-dir $dev1 --shard-dir $dev2 --shard-dir $dev3 --out results/v10_spatial_dev/h265_result.json
```

The merge verifies all 200 sources, bpp references, choices, records, model-weight fingerprints, code revisions and input provenance; it then performs 2,000 paired source-video draws. Its GO is developmental only. On NO-GO, retain the complete negative report and stop. No command in this pipeline accepts TEST or holdout as a stage.

## 4. Test and artifact checks

```powershell
& $py -m pytest tests/test_v10_spatial_gate.py -q
& $py -m pytest -q
```

On this Windows host, pytest's default legacy temp directory can be inaccessible. Use `--basetemp` with a newly named directory under the workspace, verifying the path is new first; pytest may clear an existing basetemp. This is an environment workaround, not a test skip. The synthetic tests do not download weights or access real source video labels.

Keep raw archives, manifests, JSONL records, merged JSON and sidecar hashes. Execution commits and protocol/input hashes are embedded in manifests and result JSON. The final result is measured on reused DEV, so a new source-disjoint holdout requires its own protocol, source lock and a single subsequent run. Full V10 deployment runtime remains CHƯA ĐO: current timings cover the proxy encode/decode trials and assessment inference, not the historic encoder inference that produced V2/V6 decisions.
