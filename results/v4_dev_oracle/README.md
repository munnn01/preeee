# Label-aware DEV oracle: six-candidate headroom

This is the exploratory screen specified in [V4_DEV_SCREENING_PLAN.md](../../docs/V4_DEV_SCREENING_PLAN.md), committed **before** calculation. It uses the 200-source DEV cache per codec and may inspect the true correctness of both development analyzers for every candidate. The oracle picks the lowest-bpp candidate that does not turn an identity-correct prediction into an incorrect one. It is **not deployable** and must never be treated as a frozen policy or a holdout result. No V2/V3 holdout, old TEST, or `mc3_18` record was read.

| Codec | Analyzer | Oracle BD-rate Top-1 vs identity | BD-accuracy, pp |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | −27.39% | +14.10 |
| H.264 | `r3d_18` | −26.54% | +12.47 |
| H.265 | `r2plus1d_18` | −18.12% | +13.72 |
| H.265 | `r3d_18` | −15.68% | +10.32 |

There are 1,000 video/QP rows per codec. A non-identity candidate both preserved all originally correct predictions and saved rate in **918/1,000 H.264 rows** and **925/1,000 H.265 rows**. The oracle selected identity in only 82 and 75 rows, respectively. These are point estimates on DEV; no confidence interval was preregistered for this diagnostic (`bootstrap_draws=0`). The result suggests room for a better **label-free selector** among the existing transforms, but cannot demonstrate that such a selector can learn the oracle's decisions.

The full five-QP curves, candidate counts and input hashes are in [h264_result.json](h264_result.json) (SHA-256 `a1d0911d2bd7491e37fde19dd2b67559be5fb3f6f53d5d88fd7174a726cfe388`) and [h265_result.json](h265_result.json) (SHA-256 `5790ba9dd59a1ee12230124ee409ce95badd18ac59b0d1d844806e0e6fabdc21`). The plan commit is `16e7cdf78b85d91328bb60f1237c4768d2a5a6ae`, analysis code commit is `1901af8` (full hash in each JSON), DEV source fingerprint is `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`, and [SHA256SUMS.txt](SHA256SUMS.txt) covers the package. Any deployable V4 policy needs separate preregistration, development-only fitting, freeze and a new source-disjoint holdout.
