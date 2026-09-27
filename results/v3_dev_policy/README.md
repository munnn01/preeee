# V3 per-analyzer risk thresholds: DEV-only search

This is the first and only run of the 81-policy grid locked in [PREREGISTRATION_V3.md](../../docs/PREREGISTRATION_V3.md). It reused the original V2 pilot development cache: 400 fit, 200 calibration, 200 DEV source videos per codec. The old V2 TEST, the completed V2 holdout and `mc3_18` were excluded from fitting and policy selection. The source-ID sets are pairwise disjoint and have zero overlap with the V2 holdout IDs.

**Outcome: no V3 policy was promoted in either codec.** All 81 grid policies were feasible on calibration, but the best worst-analyzer BD-rate gain over frozen V2-C was smaller than the preregistered **1.00 percentage-point** promotion margin. The frozen V2-C policy remained the fallback. The DEV calculation therefore reports the old policy again; it is **not** evidence for a new policy. The preregistered go/no-go condition failed and **no V3 holdout has been selected, labelled or evaluated**.

| Codec | Frozen V2-C low/high risk | Best V3 grid tuple (low r2, low r3, high r2, high r3) | Calibration BD-rate r2/r3: V2-C | Best grid | Worst-analyzer gain |
|---|---|---|---:|---:|---:|
| H.264 | 0.10 / 0.20 | (0.20, 0.10, 0.30, 0.10) | −18.19% / −12.69% | −18.61% / −12.80% | 0.11 pp |
| H.265 | 0.20 / 0.10 | (0.20, 0.20, 0.30, 0.10) | −13.27% / −9.28% | −13.30% / −9.63% | 0.35 pp |

The separate [amendment](../../docs/PREREGISTRATION_V3_AMENDMENT_001.md) records that the preregistration's example V2-C tuple was correct for H.264 but not H.265. The code loaded the actual per-codec frozen policy, and the correction did not alter the grid or decision rule.

The unchanged fallback's DEV BD-rates, shown to disclose the one DEV evaluation, are below. These are **exploratory DEV** values and must not be substituted for a fresh holdout result.

| Codec | Analyzer | Frozen V2-C / fallback BD-rate vs identity (95% CI) |
|---|---|---:|
| H.264 | `r2plus1d_18` | −20.40% [−24.16%, −16.43%] |
| H.264 | `r3d_18` | −11.42% [−14.91%, −8.64%] |
| H.265 | `r2plus1d_18` | −14.87% [−17.99%, −11.37%] |
| H.265 | `r3d_18` | −8.60% [−10.92%, −6.48%] |

[h264_result.json](h264_result.json) (SHA-256 `b6d72952b074dfac48555899b7189a7627261a16b2b1ff429069f0add3725151`) and [h265_result.json](h265_result.json) (SHA-256 `d164b4527bc5f34b185f92d384bed5893f8306080a70b43693882de2c7dece5e`) contain the entire 81-policy calibration grid, the actual fallback policy, all five DEV QP curve points, direct paired comparisons, 2,000 source-video bootstrap draws with seed `20260928`, requested/valid draw counts, and input manifest/index/cache-tree SHA-256 values. The preregistration commit is `245dc868f2be32679042dbe1f8a012a43abac47c`; analysis code commit is `c0212e283b0034704bf8154884fdcaed6ef07035`. [SHA256SUMS.txt](SHA256SUMS.txt) locks this package's files without self-hashing.
