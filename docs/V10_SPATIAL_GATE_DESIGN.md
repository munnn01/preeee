# V10: spatial protection around frozen V2-C/V6 selection

This design tests whether a bounded spatial penalty can retain V6's primary-analyzer gains while reducing transfer damage. It does not predict success. [Draft protocol](PREREGISTRATION_V10_SPATIAL_GATE.md) contains the full grid, source locks and stopping rules; V10 outcomes remain **CHƯA ĐO**.

## What the architecture establishes

The [TorchVision 0.25.0 implementation](https://github.com/pytorch/vision/blob/v0.25.0/torchvision/models/video/resnet.py) gives mc3_18 a 3D stem and first residual stage, then three stages with temporal kernel size one. r3d_18 uses 3D convolutions throughout; r2plus1d_18 factors temporal and spatial convolutions throughout. This supports studying spatial fidelity, but does not prove that mc3 is uniquely or extremely sensitive to downscale. The same [research family](https://openaccess.thecvf.com/content_cvpr_2018/html/Tran_A_Closer_Look_CVPR_2018_paper.html) varies temporal modeling; it is not evidence about this selector's failure mechanism.

There is a further confound: the repo resizes every analyzer input to 112×112. Identity128 and area112 therefore do not give the analyzer different final tensor dimensions. They differ in pre-codec sampling, chroma subsampling, quantization, prediction and reconstruction, followed by a different resize path. Spatial-proxy success must be measured. The V8 negative result alone also does not isolate mask-boundary bit cost as its cause.

## Historical CAL audit, before V10 measurement

The [descriptive audit JSON](../results/v10_design_audit/historical_cal_audit.json) uses only the 200-source historical H.265 CAL cache and frozen V2/V6 choices. No mc3 result or new transform was evaluated. These are paired descriptive statistics, without confidence intervals; they must not be mixed with the 100-source V9 CAL numbers or holdout outcomes. JSON SHA-256: `653f33502ba7d159fdeae9f4b7b5a79c7b3e0670492eeb48064d4692c6e87c91`.

| QP | area112 bitrate saving vs identity, P10 / median / P90 | area112 Top-1 difference: r2 / r3 (pp) | V2→V6 area112 count, out of 200 | V2→V6 identity count |
|---:|---:|---:|---:|---:|
| 30 | 12.22 / 19.45 / 29.19% | −7.0 / −2.5 | 31→105 | 42→15 |
| 35 | 8.09 / 14.31 / 22.87% | −4.0 / +2.0 | 37→118 | 61→17 |
| 40 | 4.22 / 9.28 / 15.99% | −13.5 / −6.0 | 25→100 | 110→66 |
| 45 | 1.86 / 4.88 / 8.96% | −6.5 / −9.5 | 20→78 | 130→99 |
| 50 | 0.42 / 1.87 / 4.38% | −4.5 / −2.0 | 14→68 | 157→99 |

V6 selects area112 more often at every QP, especially QP30/35. This confirms the selection shift, not which clips caused mc3 losses. At QP≥40 the guard remains necessary: smaller rate savings do not imply smaller task losses. On this full CAL cohort, V2-C's two-primary BD-rates are −13.27% / −9.28%, while V6 gives −14.05% / −14.49%. A complete return to V2-C would miss the r3 <−10% target. V10 must retain enough useful V6 decisions while suppressing spatially damaging ones. Whether the locked proxy can identify those decisions is the central unresolved question.

## Spatial proxy

For source video i and candidate c at QP q, use the common-grid grayscale clips Y_i and Z_icq. Define horizontal/vertical forward differences G_x,G_y, and a four-neighbor interior Laplacian L. All means cover frames and the appropriate spatial support. On uint8 RGB, use OpenCV RGB2GRAY and divide by 255; upsample smaller decoded candidates to 128 with INTER_LINEAR only for proxy measurement.

\[
S_i=\langle (G_xY_i)^2\rangle+\langle (G_yY_i)^2\rangle,
\qquad E_G(Y,Z)=\frac{\sum_{d\in\{x,y\}}\langle(G_dY-G_dZ)^2\rangle}
{\sum_d[\langle(G_dY)^2\rangle+\langle(G_dZ)^2\rangle]+10^{-12}},
\]
\[
E_L(Y,Z)=\frac{\langle(LY-LZ)^2\rangle}{\langle(LY)^2\rangle+\langle(LZ)^2\rangle+10^{-12}},
\qquad D_{icq}=\tfrac12(E_G+E_L)\in[0,2].
\]

The bound follows from (a−b)^2≤2(a^2+b^2). Identity-as-pixels has zero error. Codec-only identity can have nonzero error, which is why selection uses excess over decoded identity rather than a raw cutoff. Comparing derivative arrays preserves edge location; a ratio of high-pass energies alone could score an unrelated sharp texture favorably. There is no learned extractor, label, mc3 feature or mc3 inference in the proxy.

This is an intentionally limited proxy. High-frequency noise can raise S; smooth but semantically important structure can have low S; temporal behavior is not measured; and the proxy's 128-grid differs from the final analyzer preprocessing. It cannot guarantee Top-1 preservation. The tiny denominator only stabilizes flat clips; no clipping is used to hide a large error.

## QP-conditioned admissibility and safe combination

Let R_c be measured bpp, I=identity, e_c=[D_c−D_I]_+, and s the frozen CAL quantile of S. At q≤35, high complexity (S>0 and S≥s) forces I. For other clips:

\[
\mathcal A_q=\{I\}\cup\{c:R_c\le R_I,\ e_c\le\tau_q,
\ q\ge40\ \text{or}\ 1-R_c/R_I\ge g+\lambda e_c\},
\quad\tau_q=\begin{cases}\tau&q\le35\\2\tau&q\ge40.\end{cases}
\]

Start from b=V2-C if that candidate is admissible, otherwise b=I. Let v be the frozen V6 choice. Accept v only if v∈A_q, [D_v−D_b]_+≤tau, and

\[
\Delta J=\log(R_v/R_b)+\lambda(D_v-D_b)<0.
\]

Otherwise retain b; ties retain b. The decision set contains only the V2 candidate, the V6 candidate and identity. QP-dependent admissibility, a hard spatial bound and a measured rate/spatial cost serve different roles. A candidate with higher rate than b can win only if its spatial improvement compensates in ΔJ; no candidate can exceed identity rate. Existing historical blur streams are not new proposals and are still subject to these guards.

The 81-point grid fixes three CAL complexity quantiles, three excess tolerances, three minimum saving thresholds and three spatial weights. The CAL threshold is a source-only statistic, not a mc3-fitted parameter. Feasibility uses both primary analyzers; within the feasible set the rank first minimizes mean positive spatial excess, then worst/sum primary BD-rate, then the parameter tuple. Failure to find any feasible point stops the study before DEV.

## Why local safety does not guarantee the BD-rate target

Each policy produces R_q=N^−1∑_iR_iq and A_mq=N^−1∑_i1[pred_m(i,q)=label_i]. The existing BD-rate implementation integrates polynomial log-rate curves over the shared Top-1 interval:

\[
\mathrm{BDR}=100\left[\exp\left(\frac{1}{a_h-a_l}\int_{a_l}^{a_h}
\{\log R_{V10}(a)-\log R_I(a)\}\,da\right)-1\right].
\]

Top-1 is discontinuous and task-dependent. Neither the policy's local ΔJ nor a linear interpolation between V2/V6 BD-rate values predicts the mixed policy's BD-rate. Every candidate policy therefore builds complete paired CAL curves; final DEV comparisons recompute complete curves in each source bootstrap. Non-overlap/degenerate curves remain undefined and fail the gate, as in the existing metric code.

The engineering gate has four simultaneous requirements: both primaries below −10%, mc3 below 0 with CI upper≤+1%, positive BD-accuracy for all three, and worst same-QP gap≥−1 pp for all three. The mc3 CI allowance is a practical tolerance, not statistical proof of a benefit. At n=200, one clip changes a same-QP Top-1 by 0.5 pp, so the −1 pp guard permits only two net lost correct clips at any QP. The protocol can fail even when average BD-rate improves; that is intentional.

## Execution and interpretation

Four CAL proxy jobs run without analyzers. CAL selection joins the two-primary cache, then the complete chosen policy and numeric source-complexity threshold must be committed. Four DEV jobs collect all proxy measurements and write all shard choices before loading any analyzer. The model phase reads only selected/control streams; it cannot edit decisions. Direct comparisons include identity, fixed area112, V2-C, V6 and V10. Bootstrap uses 2,000 source draws, paired across all QPs/arms/analyzers.

All 30 trial encodes per source are recorded. Those trials already correspond to the six-stream selector family; their bpp must reproduce the pinned cache. This implementation reuses V2/V6 decisions from the committed cache to isolate the new guard. Its timing excludes the historical primary inference used to obtain those decisions and cannot be advertised as total deployment runtime. A future deployment benchmark must add that cost and measure peak memory on a named machine.

This request produces a draft and executable audited pipeline. Approval/lock, fresh CAL proxy measurements, CAL selection, frozen DEV assessment and any new holdout remain subsequent steps. No new experiment is launched from a draft. [Runbook](V10_SPATIAL_GATE_RUNBOOK.md) gives the exact command sequence.
