# V9 chroma-only H.265 pilot: negative CAL result

**Decision: NO-GO under the locked V9 CAL rule.** The fixed chroma transform did not improve `mc3_18` relative to frozen V6, and it substantially weakened both primary analyzers. This is a developmental result on 100 reused V2 CAL source videos. It is **not** an independent holdout, an unseen-analyzer confirmation, or an assessment of the original two-primary <−15% gate. V9 DEV and holdout remain **CHƯA ĐO**.

The [preregistered protocol](PREREGISTRATION_V9_CHROMA_CAL.md) was committed at `56485c739e257de74b1e40d658ec77302973fd03`. The Kaggle code and frozen 100-source × five-QP V6 choice manifest were committed at `f7872f249e48e2d8f793f3315323f81cec7baf25` before evaluation. The [merged JSON](../results/v9_chroma_cal/h265_result.json) and [archive inventory](../results/v9_chroma_cal/README.md) are the numeric sources for this report.

## Direct paired BD-rate Top-1

Negative percentages mean bitrate savings at equal Top-1. Each point is computed from the full 100-source five-QP curves; the intervals are 95% percentile bootstrap intervals from 2,000/2,000 valid source-video resamples. These are **direct** comparisons, not differences of separately estimated BD-rates.

| H.265 comparison | `r2plus1d_18` | `r3d_18` | `mc3_18` |
|---|---:|---:|---:|
| Frozen V6 vs identity | −12.77% [−17.85%, −7.25%] | −14.65% [−18.86%, −10.23%] | +1.34% [−4.89%, +8.07%] |
| **V9 vs identity** | **−1.90%** [−8.58%, +5.44%] | **−5.77%** [−12.25%, −0.37%] | **+3.78%** [−2.16%, +9.85%] |
| **V9 vs frozen V6** | **+10.03%** [+4.56%, +17.33%] | **+8.89%** [+3.24%, +15.12%] | **+2.56%** [−3.60%, +8.85%] |

The V9-vs-V6 BD-accuracy Top-1 changes are −8.12 percentage points [−11.55, −4.99] for `r2plus1d_18`, −6.52 [−10.40, −2.81] for `r3d_18`, and −0.71 [−4.00, +2.73] for `mc3_18`. The V9-vs-identity BD-accuracy points for the primaries are +1.58 and +3.20 points, respectively, but their V9-vs-identity BD-rate points are above the locked −10% threshold. For `mc3_18`, V9-vs-identity BD-accuracy is −3.18 points [−6.25, −0.21].

## Every locked go/no-go condition

| Condition fixed before Kaggle evaluation | Measured value | Decision |
|---|---|---|
| Direct `mc3_18` V9-vs-V6 BD-rate point <0 **and** CI upper <0 | +2.56%; upper +8.85% | Fail |
| V9-vs-identity BD-rate <−10% on both primaries | −1.90%; −5.77% | Fail |
| V9-vs-identity BD-accuracy >0 on both primaries | +1.58; +3.20 percentage points | Pass on point estimates |
| Direct V9-vs-V6 BD-rate ≤+1.00% on both primaries | +10.03%; +8.89% | Fail |
| Worst same-QP V9−V6 Top-1 gap ≥−1.00 point on all three analyzers | −10, −9, −6 points | Fail |

Because the conditions are conjunctive, the result is **NO-GO**. The original research gate remains unchanged and is **not assessed** here: it requires both primary analyzers to have BD-rate Top-1 strictly below −15% at one codec on a suitable confirmation set. A positive `mc3_18` result at one QP would not override either gate.

## Curve-level check and interpretation

| QP | V6 bpp | V9 bpp | V9 bitrate change vs V6 | `r2plus1d_18` Top-1 V6→V9 | `r3d_18` Top-1 V6→V9 | `mc3_18` Top-1 V6→V9 |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 0.240214 | 0.238794 | −0.59% | 75%→68% | 76%→70% | 65%→63% |
| 35 | 0.169140 | 0.168568 | −0.34% | 73%→63% | 66%→57% | 51%→55% |
| 40 | 0.130858 | 0.130519 | −0.26% | 56%→48% | 54%→48% | 50%→45% |
| 45 | 0.104809 | 0.104635 | −0.17% | 39%→33% | 32%→28% | 29%→23% |
| 50 | 0.091042 | 0.090977 | −0.07% | 13%→7% | 10%→7% | 10%→8% |

At QP 35, `mc3_18` gained four correct clips out of 100, while both primaries lost nine or ten. Across five QPs, V6-correct→V9-incorrect flips outnumbered the reverse flips: 49 vs 12 (`r2plus1d_18`), 45 vs 17 (`r3d_18`), and 32 vs 21 (`mc3_18`). These are 500 paired video-QP observations per analyzer, not 500 independent source videos. The chroma edit saved at most 0.59% bitrate at a fixed QP, too little to offset the measured accuracy losses in the full rate–Top-1 curves. The single favorable `mc3_18` QP is therefore not evidence that V9 improved its BD-rate.

The transform preserved the Y array inside its RGB→YCrCb→RGB operation, but the RGB roundtrip had mean source-to-output Y absolute error `0.01050` and maximum per-video/QP mean `0.24189` on the 0–255 scale. The result is consistent with visual information needed by the analyzers being perturbed; it does not isolate a causal role for chroma because conversion, quantization and codec interactions occur together.

## Provenance and scope

Four [private Kaggle notebooks](../results/v9_chroma_cal/README.md) completed, each contributing 25 distinct sources and all five QPs. The merge verified the locked ID order, source SHA-256 values, cached identity/V6 bpp, record hashes, manifest hashes and code commit before analysis. Source fingerprint: `3c31de5d56807dbbe2560a8b98c2bc43c2f46e3294cf2dd4248d5449b5a60992`. Frozen selection SHA-256: `625abf5e964dfe969ea491e1aae530689bab2031757075542166905d21d05f24`. Merged JSON SHA-256: `853c45fafe2d62cab7845bc3231c76c066a7d3416ebb8194734cc1b949a68b4a`. Bootstrap seed: `20261006`; unit: source video with QPs, arms and analyzers paired. The environment manifests report Python 3.12.13, Torch 2.10.0+cu128, TorchVision 0.25.0+cu128, OpenCV 4.13.0, FFmpeg 4.4.2 and CUDA.

The 100 clips are the preselected second half of an old CAL set, not new independent sources. Earlier work had already exposed `mc3_18` behavior. H.264, V9 DEV, a new source-disjoint holdout, and full selector runtime were **CHƯA ĐO**. The fixed 50%/sigma-1.5 chroma arm must not be retuned on these outcomes and then assessed on the same sources as confirmation. A future proposal needs a separately preregistered development protocol and a genuinely fresh holdout before a single confirmatory evaluation.
