# V4 holdout: amendment for Git newline encoding

This is an operational repair **after** the V4 source/index lock and the first Kaggle launch. It does not change the source IDs, labels, V4 or V2 policies, models, codec candidates, QPs, gate, seed, or bootstrap analysis. The original preregistration and split/index commits remain in Git history.

The first notebooks were pinned to `78c1124d092d70ba11f3ed664194e4f747f5e3a8`. The H.265 shard 1 notebook on `baooo25r` stopped in `ops.v4_frozen.frozen_manifest()` during `ready_index`, before the primary analyzer was constructed or any codec stream was scored. Its Kaggle `primary.log` ends with `ValueError: h264 V2 comparator policy changed`; it contains no `shard_records.jsonl`. The initial launch is a technical failure, not a measured negative or positive holdout result. Other first-launch shards used the same commit and are retained in Kaggle history; their outcomes must not be used to choose or tune the policy.

The V2 comparator JSON files in the Windows checkout use CRLF bytes, while the committed Git blobs and Kaggle Linux checkout use LF bytes. All four pairs differ **only** by CRLF to LF conversion and parse to identical JSON. The original manifest pinned the Windows raw-byte SHA-256 and so rejected Kaggle's unmodified Git bytes. The repair adds the already committed Git-blob SHA-256 to the manifest and accepts exactly either recorded raw-byte hash, requiring the CRLF-normalized bytes to equal the committed Git blob. It rejects other byte or semantic changes.

| Comparator | Windows checkout SHA-256 | Git blob/Kaggle SHA-256 |
|---|---|---|
| H.264 policy | `613506cb70ef01d1e0c45103a1a8f7ed43a82b6023e7dfc2b808f8d0f768a3df` | `c1cc53880ec320c1f60951adcccd4045fb1ac8881ae3ddfa5d5741d662b82985` |
| H.264 risk model | `204a75eaa340607e0a68fc485403ae06213c7e75833f0f35c2d1075f78936c24` | `a9b80d9578ab7f74b1da28c45caa15f5f36f36d3c9fb27a69261b915059f4166` |
| H.265 policy | `0d39061a0b8de838c60553a6b112a40db4c64975ddea0f19137d6fda183fa2dc` | `10a97a207506791e6cdf40b6cf30d9521ff97ba3d34a9201dae198f777f3fc1c` |
| H.265 risk model | `bfe88bf3e523d45e0c566695843d1ee5d33731c5c2358e12a3cdc778d500ffeb` | `7b630bce3638f365048d8d2d4d918cf38d4c0f962a4370e875878e600f66c5c1` |

The repair must be committed and tested before rerunning all four shards with a **new** pinned commit and notebook slug. The repaired notebooks must use the same `configs/v4_holdout_source_audit/index.json` SHA-256 `995969ffdc943976400c67337ca3d27c95370f22040f64e2fa43169e08efe8e2`, selected source fingerprint `b72321eecafe6f81368ae22e5352f04305094634aaca2a378bac12b7cc60822b`, and bootstrap seed `20260928` with 2,000 source-video resamples. No first-launch metric may be treated as an independent holdout or used for model selection.

The already uploaded private Kaggle datasets contain only the same video ZIP and a transfer manifest pinned to the original index commit. The repaired notebook checks that this original commit is an ancestor of its new evaluation commit, verifies the original freeze-manifest SHA against that Git commit, and still checks the unchanged index, selected sources, ZIP and every video byte. This allows the identical video datasets to be reused without reuploading or changing the holdout.
