# V4 correctness selector: FIT/CALIBRATION/DEV only

This is the single V4 development run specified in [PREREGISTRATION_V4.md](../../docs/PREREGISTRATION_V4.md), locked in commit `17b036c6fb5819e67751dfd3be83193eb1097be9`. The run used code commit `3b0d8dec587aa974adf0fd51a54d472def04a475`. The source-disjoint pilot development cache contained 400 FIT, 200 CALIBRATION and 200 DEV videos per codec. The two classifiers per codec use 41 label-free features at selection time. FIT labels trained the classifiers; CALIBRATION selected one policy from the fixed 81-policy grid; DEV was evaluated once. No old TEST, V2 holdout or `mc3_18` outcome was used to fit or select V4.

Both codecs passed the preregistered CALIBRATION promotion rule. The selected policies are exactly those in the JSON files. On DEV, H.265 passed the preregistered go/no-go rule for a fresh holdout. H.264 failed its same-QP guard for `r3d_18` (−2.00 percentage points versus the required ≥−1.00). This failure is retained even though its BD-rate points improved. Neither DEV result is a confirmatory holdout result.

| Codec | Analyzer | V2-C BD-rate on DEV | V4 BD-rate on DEV (95% source bootstrap CI) | V4 same-QP minimum Top-1 gap | Go/no-go by codec |
|---|---|---:|---:|---:|---|
| H.264 | `r2plus1d_18` | −20.40% | −23.04% [−25.72%, −19.69%] | −0.50 pp | No |
| H.264 | `r3d_18` | −11.42% | −22.16% [−25.81%, −18.99%] | **−2.00 pp** | No |
| H.265 | `r2plus1d_18` | −14.87% | −15.39% [−18.03%, −12.79%] | 0.00 pp | Yes |
| H.265 | `r3d_18` | −8.60% | −12.46% [−14.47%, −10.17%] | −0.50 pp | Yes |

The direct paired V4-versus-V2-C BD-rate on DEV is −3.85% [−7.14%, −0.18%] and −12.09% [−15.41%, −8.42%] for H.264 `r2plus1d_18` and `r3d_18`; H.265 is −1.29% [−3.76%, +1.02%] and −4.22% [−6.24%, −1.97%]. These comparisons reuse DEV, so they do not establish generalization. The unchanged confirmatory gate requires both primary analyzers to have BD-rate Top-1 <−15% and BD-accuracy >0 on at least one codec. **V4 holdout: CHƯA ĐO.**

The JSON files include all 81 calibration policies, the selected policy, five-QP DEV curves, paired comparisons, 2,000 source-video bootstrap resamples (seed `20260928`), source fingerprints, manifest/index/cache hashes, model hashes, and code commit. The four `.joblib` files are fitted model artifacts, not source data. The corresponding SHA-256 values are in each JSON and `SHA256SUMS.txt`. The common source fingerprints are FIT `4c12443af5c0ef44dc5143217ab00b146e0d9090607c49393487d5decd4e4bb1`, CALIBRATION `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`, and DEV `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`.

The `frozen_policy_sha256` inside the JSON is the SHA-256 of the *local pilot cache copy* read by the V4 run. The repository's frozen V2-C config may have a different raw-byte SHA because of line endings; the actual parsed policy and the digest of the risk model were checked by the runner. Raw-byte hashes are not silently substituted.
