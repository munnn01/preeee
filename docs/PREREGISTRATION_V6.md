# Preregistration V6 — paired V2-C residual selector, DEV only

**Lock this file in Git before implementing or evaluating V6.** V4 holdout, V5 CAL, old TEST, and earlier `mc3_18` outcomes have already been seen and motivate the question. They cannot confirm V6. The FIT/CALIBRATION/DEV pilot splits have also been reused across iterations; any V6 development result is exploratory. A fresh source-disjoint holdout, with a separate ID lock and one-shot protocol, is required before a confirmatory claim. A wholly unseen-analyzer claim requires a fourth K400-compatible frozen analyzer. The original confirmatory gate remains unchanged: at least one codec with both primary BD-rate Top-1 point estimates <−15% and BD-accuracy >0 against identity.

## Question, data, and fixed arms

Can a selector that starts from V2-C and uses predicted **paired changes in correctness** reduce source-feature distortion while keeping both primary analyzers' BD-rate close to V2-C? This is a proxy hypothesis, not evidence that `mc3_18` will improve. No `mc3_18` prediction, label, output, TEST, or holdout input may be opened by this run. No new transform, codec setting, QP, encoder trial, video, or feature extractor is introduced.

Use only the original V2 pilot cache: 400 FIT, 200 CALIBRATION, and 200 DEV source videos per codec, with five QPs `30,35,40,45,50` and candidates `identity128`, `area112`, `area96`, `area112_up128`, `blur020_128`, `blur040_128`. The two codecs use the same source IDs. FIT fingerprint `4c12443af5c0ef44dc5143217ab00b146e0d9090607c49393487d5decd4e4bb1`; CALIBRATION `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`; DEV `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`. Use the committed V5 cache lock `configs/v5_dev_cache_manifest.json`, SHA-256 `5064f454b3602fe2d7e8c0adaff09c4a990622b836978d8d3c0b7c1a46b8fd9d`, and verify each cache stage and frozen V2 risk/policy input against that lock before fitting or selecting. The archive SHA-256 in the lock is `fba0149d3320398c92ecfd51a194e365b4b04832f8d4334110be19569fc15c17`. Each codec's V2-C policy and risk model are the frozen files inside that cache. Identity and V2-C are the fixed comparators; V6 is the sole candidate arm.

## FIT: paired event models

For each FIT source, QP and candidate, compute the V2-C selection using its frozen risk model and policy. For each primary analyzer (`r2plus1d_18`, `r3d_18`) and each candidate other than the V2-C selection, train two binary event models: **harm** = V2-C correct and candidate wrong; **gain** = V2-C wrong and candidate correct. Training labels are read only from FIT. Candidate predictors are the existing 41 `risk_features` values for the V2-C selection concatenated with the candidate-minus-V2-C difference of those same 41 values. The feature function exposes only the existing label-free signal allowlist, QP, candidate name, and bpp; source ID and all correctness fields are excluded from inference.

Fit four models per codec with `StandardScaler` and `LogisticRegression(C=1.0, max_iter=2000, random_state=53)`, no class weighting and no CAL/DEV fitting. If a FIT event has only one class, use a constant: harm probability 1 or gain probability 0, conservatively. The V2-C selection has harm=gain=0 by definition. Record class counts, model parameters, sklearn version, and SHA-256 of all serialized models.

## CALIBRATION: fixed 12-policy grid and selection

For each candidate and primary analyzer, calculate expected correctness change `p(gain) - p(harm)` versus the V2-C choice. A candidate is admissible only if both changes are at least `t`, where shared `t ∈ {-0.05, -0.02, 0.00}`. V2-C is always admissible. Among admissible candidates, choose the smallest score

`log(candidate_bpp / V2_bpp) + lambda * mean_model(candidate_feature_distance - V2_feature_distance)`

where `lambda ∈ {0, 5, 20, 80}` and the mean spans the two primary analyzers. Resolve equal scores by the six-candidate order above. This yields exactly 12 fixed policies per codec. The feature-distance term is measured to the clean source in the existing label-free cache; its proposed relationship to `mc3_18` is unvalidated.

On CALIBRATION, compare each policy with identity and with frozen V2-C on the same sources. A policy is feasible only if **for each primary analyzer** its finite BD-rate Top-1 versus identity is at most V2-C's CALIBRATION BD-rate plus **1.00 percentage point**, its BD-accuracy is finite and >0, and its minimum same-QP Top-1 gap versus identity is ≥−1.00 percentage point. The policy must also have a strictly smaller mean feature distance to the clean source than V2-C, averaged equally over source videos, QPs and the two primary analyzers. Select the feasible policy with the smallest mean feature distance; tie-break by lower worse-of-two BD-rate, then lower sum BD-rate, then `(t, lambda)` ascending. This proxy is a development selection criterion, not a claim of transfer.

Report all 12 grid rows, choice counts and V2-C comparator curves. If none is feasible, report a negative CAL result and **stop before DEV**. Do not change this grid, tolerance, proxy or tie-break after seeing CAL.

## DEV readout and stop

If CAL selects a policy, freeze its two parameters and evaluate the 200 DEV sources exactly once. Compute full curves, direct paired V6 versus identity and V2-C BD-rate and BD-accuracy, same-QP gaps, feature-distance delta and choice counts. Bootstrap **2,000** times with seed `20260930` by **source video**, keeping QPs, arms and analyzers paired. Report percentile 95% intervals for the two direct comparisons and for the mean per-source feature-distance delta. Do not alter `src/metrics/bd_rate.py` or bootstrap logic.

DEV go/no-go for a future holdout proposal requires both primary analyzers' BD-rates versus identity to remain within **+1.00 percentage point** of V2-C, both BD-accuracies >0, both minimum same-QP gaps ≥−1.00 point, and mean source-feature distance below V2-C. A failed condition is a developmental negative result. No holdout is run or selected by this protocol. Any later candidate with a new transform or added analyzer needs a new preregistration and fresh data lock.

Each result must record preregistration and analysis commits, SHA-256 of input manifest/cache, frozen V2 risk/policy and fitted models, source fingerprints, seed, bootstrap unit and draws, result SHA-256, and the exact CAL/DEV stop decision. The private Kaggle notebook must clone a full pinned Git commit and contain no credentials or holdout inputs. No result is asserted until its completed artifact is inspected.
