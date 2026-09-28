# V5 agreement guard: developmental CAL result

## Decision under the locked protocol

The private Kaggle notebook `shungg05/v5-dev-agreement-12a37e4` finished using [the locked V5 protocol](PREREGISTRATION_V5.md) and the [technical input-layout amendment](V5_DEV_TECHNICAL_AMENDMENT.md). The CAL grid contained all 81 registered threshold tuples for each codec. **No tuple met the registered constraints for either codec (0/81, 0/81).** Thus no V5 policy was promoted. The runner stopped before DEV as prescribed. **DEV: CHƯA ĐO. New holdout: CHƯA ĐO. `mc3_18` for V5: CHƯA ĐO.** There is no V5 confirmatory gate result.

The rate constraint was BD-rate Top-1 versus identity no worse than frozen V2-C on this CAL set plus 1.00 percentage point **for each** primary analyzer. The additional locked requirements were BD-accuracy >0 and minimum same-QP Top-1 gap ≥−1.00 percentage point. The table below reads directly from the original Kaggle [H.264 JSON](../results/v5_dev_agreement/results/h264_result.json) and [H.265 JSON](../results/v5_dev_agreement/results/h265_result.json). “Best V5 in grid” is a descriptive minimum over all 81 **ineligible** tuples, not a selected policy.

| Codec | Primary analyzer | V2-C CAL BD-rate | V5 rate bound | Best V5 in grid | Tuples meeting rate bound |
|---|---|---:|---:|---:|---:|
| H.264 | `r2plus1d_18` | −18.19% | ≤−17.19% | −10.13% | 0/81 |
| H.264 | `r3d_18` | −12.69% | ≤−11.69% | −11.72% | 1/81 |
| H.265 | `r2plus1d_18` | −13.27% | ≤−12.27% | −6.64% | 0/81 |
| H.265 | `r3d_18` | −9.28% | ≤−8.28% | −8.17% | 0/81 |

The weakest threshold tuple `(-0.05, -0.05, -0.05, -0.05)` yields those grid minima for both analyzers in both codecs. Its minimum same-QP gap is 0 on CAL, but it chooses identity for 407 of 1,000 source×QP decisions with H.264 and 479 of 1,000 with H.265. This is a descriptive explanation for the lost bitrate advantage; the tuple remains **ineligible** and cannot be advanced by loosening the +1.00 point bound after seeing CAL. The full grid, including BD-accuracy and choice counts for every tuple, remains in the JSON.

## Provenance and scope

The preregistration commit is `bca2f7ce26c8b741c124d878a714495b4897c789`; the analysis code commit is `12a37e4080413dc4029e957ff9d93ece39518761`. The V5 cache manifest SHA-256 is `5064f454b3602fe2d7e8c0adaff09c4a990622b836978d8d3c0b7c1a46b8fd9d`. The archived output SHA-256 and per-result hashes are recorded in [the result package](../results/v5_dev_agreement/README.md), with the raw archive and `SHA256SUMS.txt`. The result JSON includes hashes for the V4 model/config, V2 pilot input, each cache stage, and FIT/CAL/DEV source fingerprints. The `frozen_policy_sha256` values identify archived cache inputs; they should not be mistaken for hashes of current working-tree policy files.

The registered bootstrap unit is source video, with 2,000 resamples and seed `20260929`. Since no policy passed CAL, no DEV bootstrap or CI was computed. The result JSON truthfully sets `dev` to `null`. The run used only the two primary analyzers in the original V2 pilot FIT/CAL/DEV cache. It did not open `mc3_18` outcomes or a new holdout. V4 and prior holdouts had already been viewed before this developmental question was registered, so they cannot independently validate V5.

This report uses the unmodified Kaggle output as the authoritative result.
