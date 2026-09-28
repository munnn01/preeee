# V8 H.265 CAL-only pilot artifacts

The four private Kaggle jobs each measured 25 of the first 100 IDs in the locked V2 CAL order. The [merged result](h265_result.json) contains source IDs and source-video SHA-256, all five QP curves, three-analyzer comparisons, 2,000 source-video bootstrap resamples, seed, source fingerprint, commit hashes, shard manifests and records SHA-256. `h265_result.sha256` verifies that JSON. The four archives contain per-source measurements, manifest, per-source checkpoints and run log; they contain **no source video** or credential.

| Shard | Kaggle account | Archive | SHA-256 |
|---:|---|---|---|
| 0 | shungg05 | `archives/v8_motion_pilot_shard0.tgz` | `2801a7b2049287c465c1e6b012455ea5120a12688af1d3ab28926fe9ed23fa6e` |
| 1 | dieulinhh | `archives/v8_motion_pilot_shard1.tgz` | `df998cc8d78b73f66f5a586ff7e62e3b65044ea506cb16667c4cdd520aa09bf2` |
| 2 | huolgggnuyen | `archives/v8_motion_pilot_shard2.tgz` | `3c3565c9e2320d95c402e362e312104b0413585b0667ee1c8ab61af56170b095` |
| 3 | baooo25r | `archives/v8_motion_pilot_shard3.tgz` | `3317e90e1ede8267d9836409125ebfcaa463db717640b19d3a963a767c37d6a5` |

See [the result interpretation](../../docs/RESULTS_V8_MOTION_CAL.md) and [locked protocol](../../docs/PREREGISTRATION_V8_MOTION_PILOT.md). This is reused CAL development evidence only; no holdout claim is made.
