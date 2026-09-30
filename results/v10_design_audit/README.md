# Historical CAL design audit for V10

`historical_cal_audit.json` is a descriptive reanalysis of the existing 200-source H.265 V2 CAL cache, generated before V10 measurements. It contains paired per-QP identity/area112 rate-saving quantiles, two-primary Top-1 differences, and frozen V2/V6 choice counts. It does not contain V10 outcomes or mc3 measurements. Bootstrap draws are explicitly zero for this descriptive audit; no confidence interval or confirmatory claim is made. The later V10 assessment protocol uses 2,000 draws.

The JSON records its execution commit, source fingerprint, seed, cache-lock SHA-256 and complete H.265 cache/index/config tree hashes. Source-video hashes are in the committed `configs/v10_spatial_plan.json`, whose SHA-256 is `bb4b9aa245ff2d8b5f92cb1a45dedb65adfc8a664543878bb7b9cdb1486b421e`. JSON SHA-256: `653f33502ba7d159fdeae9f4b7b5a79c7b3e0670492eeb48064d4692c6e87c91`.

Read the [design interpretation](../../docs/V10_SPATIAL_GATE_DESIGN.md) and [draft protocol](../../docs/PREREGISTRATION_V10_SPATIAL_GATE.md). This cohort has 200 sources and must not be treated as the 100-source V9 pilot or a holdout.
