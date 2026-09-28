# V8 motion-protected preprocessing: CAL-only pilot protocol

Status: locked before code execution on Kaggle. This is a **development screen**, not a new holdout or independent-analyzer confirmation. Prior V2/V6/V7 outcomes, including `mc3_18`, have been seen and motivated the design. The original confirmatory gate (BD-rate Top-1 strictly below -15% for both primary analyzers in at least one codec) is unchanged. This pilot cannot establish that gate.

## Question and fixed inputs

Does smoothing temporally quiet pixels while protecting moving content give a better H.265 rate/action-accuracy tradeoff than uniform blur or fixed downscaling? This tests a pre-codec pixel transform with the standard H.265 encoder and unchanged frozen analyzers. It does not claim the general idea of preprocessing or region-aware bit allocation is new.

Use only the **first 100 IDs in the existing V2 CALIBRATION order** of `configs/v7_dev_proxy_plan.json`, SHA-256 `5b0a32d1d0a1759b50232f0c297ee35ee5cfe0cfdf00c53b587781baa5afebc2`. These are reused development sources. No FIT, DEV, previous TEST or holdout video may be loaded. Four deterministic shards use positions `0::4`, `1::4`, `2::4`, `3::4` within these 100 IDs (25 source videos each). Resolve exact `class/file.mp4` IDs uniquely and hash each source video. Fail on missing/duplicate/undecodable sources. Labels come only from the Kinetics-400 folder name for evaluation, after preprocessing and encoding; no learning or selection uses labels. Decode the same centered 16-frame, stride-2, 128×128 RGB clip as the V2 pilot.

## Four arms, fixed before data

1. `identity128`: source clip unchanged.
2. `area112`: OpenCV `INTER_AREA` from 128×128 to 112×112, the fixed spatial baseline.
3. `blur040_128`: existing candidate from `make_candidates`, 40% blend toward Gaussian sigma 1.5; a uniform smoothing control.
4. `motionprotect128`: one fixed pre-codec transform. Convert source RGB to grayscale uint8. For each frame, define motion as the maximum absolute grayscale difference from its available temporal neighbors. Across all 16 frames and pixels take the 80th percentile; protect pixels strictly above it. Dilate each frame's binary mask with a 5×5 all-ones square, then Gaussian feather the mask with sigma 1.0. Apply RGB Gaussian blur sigma 1.5 to the source; output `round(mask*source + (1-mask)*blur)`, clipped to uint8. No detector, optical flow, learned model or transmitted mask. If all frames are static, the protected mask is empty. No per-source or per-QP parameter changes.

Encode/decode every arm at QP 30, 35, 40, 45, 50 with `StandardCodec('h265', preset='medium', strict_decode=True)`. Count actual coded bytes; normalize all bpp to the original 128×128 pixel count. Score the decoded streams with frozen torchvision Kinetics-400 `r2plus1d_18`, `r3d_18`, `mc3_18`, clip size 112. Require identical class order, record model/FFmpeg versions, exact source hashes, source ID, code commit, source-plan hash, arm, QP, coded bytes, bpp, Top-1 outcome, and encoder/inference timings. All analyzers are **development outcomes** here, including `mc3_18`.

## Locked analysis and decision

Merge all 100 source records, then average bpp and Top-1 across sources at each QP before computing BD-rate Top-1 and BD-accuracy. Direct comparisons are `motionprotect128` versus each of identity, `area112`, and `blur040_128`; also report each control versus identity. Do **not** subtract independently calculated BD-rates. Use 2,000 percentile bootstrap resamples of **source video** with seed `20261005`; retain all five QPs, four arms and three analyzers together per sampled source. Report point estimates, 95% intervals, valid-draw counts, worst same-QP Top-1 gap, and raw curves for every comparison. Reject incomplete, duplicate, out-of-plan or cross-shard records; merge raw source curves, never average shard BD-rates.

The pilot supports further development only if `motionprotect128` has point BD-rate Top-1 < 0 versus identity for **all three analyzers**, and no analyzer's worst same-QP Top-1 gap is below -1 percentage point versus identity. A stronger, separately reported technical target is point BD-rate < -10% on each primary analyzer; it does not alter the original < -15% confirmatory gate. A failed condition is a negative pilot. Even a pass only motivates a separately preregistered DEV experiment; it cannot be called holdout success. Do not tune any transform coefficient on these 100 results and relabel the same cohort as confirmation. Any later change requires a new dated development protocol. Existing `src/metrics/bd_rate.py` and bootstrap logic remain untouched.

Each JSON artifact must include code commit, this preregistration commit, SHA-256 of this protocol and source plan, source fingerprint, source-video hashes, seed, bootstrap unit and draws, and a SHA-256 sidecar for the result. Kaggle notebooks stay private. No unmeasured number may be presented as a result.
