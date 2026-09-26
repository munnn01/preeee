# Frozen V2-C versus fixed downscaling on old DEV

These are **exploratory DEV** results from the original V2 pilot cache: 200 paired source videos, fingerprint `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`, identical IDs for both codecs. The frozen policy and each fixed transform were evaluated on the same six real-codec candidate measurements at QP 30/35/40/45/50. The two comparators, `area96` and `area112`, were specified in `docs/PREREGISTRATION.md`; neither was chosen from TEST. CI uses 2,000 paired whole-video bootstrap draws with seed `20260924`.

| Codec | Analyzer | V2-C vs identity | area96 vs identity | area112 vs identity |
|---|---|---:|---:|---:|
| H.264 | `r2plus1d_18` | −20.40% | +4.71% | −3.09% |
| H.264 | `r3d_18` | −11.42% | +8.28% | +1.43% |
| H.265 | `r2plus1d_18` | −14.87% | +2.14% | −2.63% |
| H.265 | `r3d_18` | −8.60% | +12.99% | +0.45% |

The direct paired comparisons below use each downscale arm as the anchor. A negative number favors V2-C; **these are not differences of the preceding BD-rates**.

| Codec | Analyzer | V2-C vs area96, 95% CI | V2-C vs area112, 95% CI |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | −21.68% [−28.24%, −14.36%] | −17.09% [−22.63%, −11.26%] |
| H.264 | `r3d_18` | −18.72% [−24.58%, −12.06%] | −12.92% [−18.50%, −7.07%] |
| H.265 | `r2plus1d_18` | −12.93% [−16.07%, −8.07%] | −11.53% [−15.32%, −7.23%] |
| H.265 | `r3d_18` | −17.48% [−21.29%, −13.38%] | −8.68% [−12.27%, −4.88%] |

This supports a contribution beyond fixed spatial downscaling **on DEV only**. It is not a confirmatory holdout result. The V2-C versus identity point estimates were independently checked against the original `pilot_result.json` in each pilot archive and match to absolute tolerance `1e-12`.

`h264_result.json` and `h265_result.json` contain every QP curve, fixed-arm and direct comparisons, CI, cache-tree/manifest/archive/index SHA-256, source pilot commit, analysis commit, seed and source-video bootstrap unit. Their SHA-256 values are in `SHA256SUMS.txt`.
