# V12 spatial: Kaggle launch record

Worker commit `17cc33f81a1d685574dc1a11956b12f89b1b59ab`; preregistration commit `1a734e9228644c1cf13deeb517995593d295fb8a`. Four private notebooks were successfully pushed and the authenticated API reported RUNNING for all four at `2026-09-30T11:59:37.095308+00:00`. This is a dated status snapshot, not a completion claim. See [submission receipt](../results/v12_lowqp_launch/launch_receipt.json) and [status snapshot](../results/v12_lowqp_launch/status_snapshot.json).

| Shard | Account | Notebook | Snapshot |
|---|---|---|---|
| 0 | shungg05 | [50 sources](https://www.kaggle.com/code/shungg05/v12a-spatial-cal-s0-17cc33f) | RUNNING |
| 1 | dieulinhh | [50 sources](https://www.kaggle.com/code/dieulinhh/v12a-spatial-cal-s1-17cc33f) | RUNNING |
| 2 | baooo25r | [50 sources](https://www.kaggle.com/code/baooo25r/v12a-spatial-cal-s2-17cc33f) | RUNNING |
| 3 | trnhlng | [50 sources](https://www.kaggle.com/code/trnhlng/v12a-spatial-cal-s3-17cc33f) | RUNNING |

Exactly 200 reused CAL source videos, 50 per shard, fingerprint `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`. Planned unique encode/decode trials: 2235; actual completed trials: CHƯA ĐO. Spatial uses CPU; semantic requires GPU and verifies frozen ResNet18 checkpoint/state hashes. All notebook payloads and submission logs are committed under `results/v12_lowqp_launch/` with SHA-256 in its artifact manifest.

Two initial attempts stopped before `kernels push`: nonexistent-slug status lookup and malformed owner-list metadata. Failed payloads/logs/receipts are preserved in the spatial repo. The six verified accounts run eight notebooks in total; existing successful jobs were not resubmitted. See [technical amendment](V12_PUBLISHER_TECHNICAL_AMENDMENT.md).

Tests: original implementation whole suite 532 passed / 4 warnings; after publisher repair, all 19 V12 tests passed. The whole suite was not rerun after that isolated repair. [Evidence](../results/v12_lowqp_launch/testing/test_results.json).

No CAL results are merged yet. BD-rate, BD-accuracy, same-QP gaps, CIs, MC3, fresh DEV, holdout and total encoder overhead are **CHƯA ĐO**. No gate success is claimed. After four raw archives validate, local calibration uses the locked primary CAL outcomes, unchanged BD/paired-bootstrap functions, 2,000 source-video draws and seed 20261009. CAL intervals are descriptive after selection. NO-GO stops this direction; a chosen policy must be committed before a separately registered fresh DEV study. Both alternatives share sources and are not independent replications. No holdout evaluation or MC3-based selection has been launched.
