# V10 H.265 spatially guarded selector — locked preregistration

PREREGISTRATION_LOCKED: true

Status: locked for the user-requested V10 Kaggle deployment on 2026-09-30, before V10 CAL collection. The fixed source plan and tested implementation are committed. V10 measured results, selected parameters and holdout: **CHƯA ĐO**.

## Hypothesis, evidence and scope

Starting with the frozen V2-C decision, a QP-conditioned guard based on source spatial complexity and decoded spatial error may preserve transfer performance when accepting a frozen V6 decision. Architecture motivates this hypothesis; it does not establish that area112 at low QP caused previous mc3 losses. Past CAL/DEV and mc3 outcomes have been observed. This is congeneric development on reused K400 sources under the same H.265 protocol, not independent confirmation. The original two-primary BD-rate <−15% gate is unchanged.

## Fixed inputs and source locks

`configs/v10_spatial_plan.json` exact SHA-256: `bb4b9aa245ff2d8b5f92cb1a45dedb65adfc8a664543878bb7b9cdb1486b421e`. The plan contains 200 CAL and 200 DEV source IDs and video SHA-256 from the committed V7 extraction, disjoint by source ID and file hash. Source fingerprints follow the historical `digest(ids)` convention:

| Input | SHA-256 |
|---|---|
| CAL ID fingerprint | `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721` |
| DEV ID fingerprint | `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258` |
| Original V7 source plan | `5b0a32d1d0a1759b50232f0c297ee35ee5cfe0cfdf00c53b587781baa5afebc2` |
| V5 cache lock | `5064f454b3602fe2d7e8c0adaff09c4a990622b836978d8d3c0b7c1a46b8fd9d` |
| Frozen V6 manifest | `bedb316eacf9167a6db2b766c1b00aef5cf5dcaa333ae65e56c2333349e0eadb` |
| V7 CAL source records | `c7e62d72b97cf7bcdc739008ad1d95dddc8c75f7e75e8a577cc2517222e1d2d0` |
| V7 DEV source records | `f20263168c67dd5f275bad9ebc3ff3ef212b9f300e601bc4dd88dde05720a17f` |

SHA-256 above means exact Git blob bytes. Source videos use exact file bytes; Markdown/code permit CRLF only for comparing a checkout to its Git blob. V2-C H.265 frozen policy has Git-blob SHA-256 `10a97a207506791e6cdf40b6cf30d9521ff97ba3d34a9201dae198f777f3fc1c` and historical CRLF-file SHA-256 `0d39061a0b8de838c60553a6b112a40db4c64975ddea0f19137d6fda183fa2dc`; these refer to different byte representations, not interchangeable hashes. The V6 loader checks its four model hashes and existing development provenance. No V6 refitting is performed.

All four shards use positions `shard::4` within the locked stage order, giving 50 sources per shard. Source IDs and byte hashes must match before decoding. CAL and DEV are development partitions; no old TEST, old holdout, new holdout, alternate source or replacement for an unreadable video is permitted. Incomplete sources, codec failures, hash mismatch or undefined required metrics cause an explicit incomplete/NO-GO result.

## Fixed policy family

Source clips: deterministic centered 16 frames, stride 2, RGB uint8 128×128, as in V2/V6. Codec: H.265/libx265, medium, strict decode, QPs 30/35/40/45/50. Retain exactly the six historical candidates. V10 introduces no new filter or color transform; legacy blur candidates remain only if selected by V2/V6 and admitted by the guard. Bpp always uses original 16×128×128 pixels.

Let Y be source grayscale in [0,1], and Z_c the decoded candidate resized to 128×128 by OpenCV INTER_LINEAR when needed. Grayscale uses OpenCV RGB2GRAY on uint8 then division by 255. Use forward horizontal/vertical differences and a four-neighbor Laplacian on interior pixels. Spatial complexity S is mean squared horizontal gradient plus mean squared vertical gradient. Define normalized squared gradient error E_g as the sum of mean squared gradient differences divided by the sum of source and decoded gradient energies plus 1e−12; E_l is the analogous Laplacian error. D_c=(E_g+E_l)/2 lies in [0,2]. No label, classifier feature, mc3 prediction or mc3 weight is used in S or D.

For policy (p,tau,g,lambda), the complexity threshold s is the linear p-quantile of the 200 CAL S values and is frozen numerically for DEV. Let e_c=max(0,D_c−D_identity) and saving_c=1−R_c/R_identity.

1. Identity is always admissible. At QP≤35, if S>0 and S≥s, force identity, with no rate override.
2. Otherwise a nonidentity candidate is admissible only if R_c≤R_identity and e_c≤tau at QP≤35, or e_c≤2tau at QP≥40. At QP≤35 also require saving_c≥g+lambda*e_c.
3. Set b to the V2-C choice if admissible, else identity. Consider only the frozen V6 choice v. Switch b→v only if v is admissible, max(0,D_v−D_b)≤tau and log(R_v/R_b)+lambda*(D_v−D_b)<0. Ties retain b. Return b otherwise. No label/correctness field is accepted by this selection interface.

Exactly 81 configurations: p∈{0.50,0.75,0.90}; tau∈{0.02,0.05,0.10}; g∈{0.05,0.10,0.20}; lambda∈{0.5,1.0,2.0}. No additional grid, proxy, coefficient fitting, adaptive search or manual candidate promotion after CAL results. Constant zero-complexity clips are not classified as high complexity merely because a quantile is zero.

## Sequence and CAL selection

1. Lock/commit protocol and source plan; prepare a CAL manifest from the locked V2 cache with only candidate bpp and V2/V6 choices, then commit that manifest. Its SHA-256 and preparation commit are carried by every shard.
2. Run four CAL **proxy-only** shards. Encode/decode all six candidates at all five QPs, record S and D, coded bytes, decoded-frame SHA-256 and timings. Require bpp within 1e−9 of the committed cache for every candidate. This phase constructs no analyzer and reads no labels.
3. Validate/merge all four CAL proxy shards in locked source order. Join only the historical two-primary CAL correctness cache. Report by-QP identity-vs-area112 paired rate saving quantiles (10/50/90%), spatial excess quantiles and both primary Top-1 differences; report V2/V6/V10 choice counts by QP. These are development diagnostics, not mc3 evidence.
4. A grid policy is CAL-feasible only when both primaries have BD-rate vs identity <−10%, BD-accuracy >0 and worst same-QP Top-1 gap ≥−1.00 pp. Rank feasible policies lexicographically by mean positive spatial excess over identity (smaller), worst primary BD-rate (smaller), sum of primary BD-rates (smaller), then (p,tau,g,lambda). All means give equal weight to source and QP. Report the complete grid. CAL mc3 outcomes are unavailable to the selector. If no feasible policy exists, record NO-GO and stop before DEV.
5. Commit the complete CAL result and selected numeric threshold/parameters before preparing any new V10 DEV input. The existing V6 loader may verify its historical DEV artifact to establish frozen model identity; V10 does not select parameters from it. DEV pixel source hashes may be inspected in advance; DEV primary correctness is not used until policy freeze.
6. Prepare/commit a DEV input manifest under the frozen CAL result. Run four DEV shards. Compute all six candidate proxies and all per-source QP decisions before creating the three analyzers or reading that source's label. Score identity, fixed area112, V2-C, V6 and V10. Shared streams share identical predictions. The policy is evaluated once on this DEV cohort and is not changed after mc3 is revealed. A failed developmental assessment is reported as negative.

## Locked analysis and go/no-go

Merge records before building five-point curves. Report V2-C/identity, V6/identity, area112/identity, V10/identity, V10/V2-C and V10/V6, each directly for all three models. Use the existing BD-rate/BD-accuracy implementation and existing `ops.v8_motion_pilot.summarize` unchanged. Bootstrap 2,000 percentile draws with numpy default_rng seed **20261007**, unit **source video**, retaining all QPs, arms and analyzers in each draw. Use the same resample matrix for every comparison. Report requested/valid draws and 95% CI even when negative or undefined; undefined points fail. Require at least 1,900 valid BD-rate and BD-accuracy draws per analyzer in the primary V10/identity assessment, otherwise label the gate inconclusive/NO-GO.

V10 developmental GO requires **all**: (a) each primary V10/identity BD-rate <−10%; (b) mc3 V10/identity BD-rate <0 and upper endpoint of its two-sided 95% CI ≤+1%; (c) BD-accuracy >0 on all three; (d) worst same-QP V10−identity Top-1 gap ≥−1.00 pp on all three. This CI criterion allows a small positive upper bound and is not a claim of statistically significant improvement. The original <−15% two-primary point gate is reported descriptively on DEV without calling it confirmatory. Neither gate is relaxed if unsuccessful.

Every manifest/result includes the execution Git commit, protocol commit and SHA-256, source-plan SHA-256, input manifest SHA-256, code fingerprint, stage source fingerprint, video hashes, seed and resample count. Each raw record and result has an external SHA-256 inventory (a file cannot contain its own byte hash). Record library/FFmpeg versions, device, all 30 trial encode/decode calls and timings; these are proxy-stage measurements, not the full runtime of V2/V6 selection, whose inference cost is not remeasured here.

Fresh source-disjoint confirmatory holdout and its fingerprint are **CHƯA CHỐT / CHƯA ĐO**. Any future holdout requires a separate preregistration and commit before one evaluation. mc3 remains a transfer analyzer with previously observed history; it cannot be described as a never-observed independent architecture.
