# V8 motion-protection pilot: negative CAL result

**Decision: NO-GO under the locked CAL-only rule.** The fixed motion-protected preprocessor did not improve H.265 BD-rate Top-1 against identity on any of the three analyzers. Positive BD-rate means **more** bitrate at equal Top-1. This is a developmental result on 100 reused V2 CAL sources, not a new holdout or independent `mc3_18` confirmation. The original two-primary gate (<−15% at one codec) is **not assessed** by this pilot and remains unchanged.

The protocol and literature audit were committed at `cb259971bd2dc6f201eeab14fa7d7af7a04a627e`; the exact code used by Kaggle was committed at `209c70a9fd1efb4d62fb63c42537abd802a1eb68`. [Preregistration](PREREGISTRATION_V8_MOTION_PILOT.md), [literature audit](LITERATURE_V8_MOTION.md), [merged JSON](../results/v8_motion_cal/h265_result.json), [archive inventory](../results/v8_motion_cal/README.md).

| H.265 direct paired comparison, BD-rate Top-1 | `r2plus1d_18` | `r3d_18` | `mc3_18` |
|---|---:|---:|---:|
| **Motion-protected vs identity** | **+9.97%** [1.51%, 17.45%] | **+12.18%** [3.44%, 20.80%] | **+13.90%** [4.10%, 24.36%] |
| Motion-protected vs area112 | +12.86% [3.03%, 20.78%] | +17.46% [8.23%, 28.19%] | +12.79% [4.59%, 20.75%] |
| Motion-protected vs uniform blur | +0.58% [−7.02%, 8.00%] | +4.14% [−4.89%, 13.01%] | +1.71% [−5.56%, 11.13%] |
| area112 vs identity | −3.15% [−9.01%, 2.99%] | −7.38% [−13.75%, −1.38%] | −2.20% [−7.74%, 5.17%] |
| Uniform blur vs identity | +8.62% [2.61%, 13.81%] | +8.36% [0.69%, 15.53%] | +9.46% [2.01%, 17.01%] |

The motion-protected arm also had negative BD-accuracy against identity: −6.80 percentage points [−11.40, −2.05] on `r2plus1d_18`, −7.86 [−12.27, −3.59] on `r3d_18`, and −6.69 [−11.55, −2.30] on `mc3_18`. Its worst same-QP Top-1 gaps were −10, −16, and −8 percentage points respectively, each below the locked −1 point tolerance. The stricter engineering target of BD-rate <−10% on both primaries also failed.

For a direct curve check, at QP 30 on `mc3_18`, identity used 0.275850 bpp at 62% Top-1 and motion protection used 0.277732 bpp at 55% Top-1. The transform protected a mean 45.47% of pixels after mask dilation, yet lost action accuracy. This is consistent with the mask/blur combination disrupting relevant visual structure; it is not a causal attribution. The next study must use a separate preregistration and cannot retune this fixed arm on these 100 outcomes while presenting the same sources as confirmation.

All four Kaggle notebooks completed: [shard 0](https://www.kaggle.com/code/shungg05/v8-motion-cal-s0-209c70a), [shard 1](https://www.kaggle.com/code/dieulinhh/v8-motion-cal-s1-209c70a), [shard 2](https://www.kaggle.com/code/huolgggnuyen/v8-motion-cal-s2-209c70a), [shard 3](https://www.kaggle.com/code/baooo25r/v8-motion-cal-s3-209c70a). Each contributed 25 distinct source videos. Their manifests report Python 3.12.13, Torch 2.10.0+cu128, TorchVision 0.25.0+cu128, OpenCV 4.13.0, FFmpeg 4.4.2, and CUDA. Every one of the 100 video SHA-256 values matched the earlier V7 CAL extraction. Source fingerprint: `e4134a770101dad6c45e2caf028665349af302d27bd2e8af4427260a93e55f31`. The merge validated all shards and computed full-source curves before BD-rate; every CI used 2,000/2,000 valid percentile resamples, seed `20261005`, unit **source video**, with all QPs, arms and analyzers paired. [Merged JSON](../results/v8_motion_cal/h265_result.json) SHA-256: `3c8f59bb5861e8ef3be571c85075c4fb722d7134c6bf53e88650e98ec786e207`. No DEV, previous TEST or holdout evaluation was run for V8.
