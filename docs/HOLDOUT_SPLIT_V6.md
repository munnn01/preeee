# V6 H.265 holdout: source audit status

**Status: 1,000 source IDs, video hashes and label index are locked; all V6 holdout analyzer outcomes remain CHƯA ĐO.** The new [preregistration](PREREGISTRATION_V6_HOLDOUT.md) was committed at `385674ddf93d477d78f0b6b1b4abdff667eee7e5`, before this candidate ranking. The H.265 V6 freeze and audit code were committed at `67067adefeaddda326c9f9c3f6c7560acbc79a9b` before ranking.

The official CVDF Kinetics-400 validation annotation (SHA-256 `358eaf47e7f80ebf9b17d49eb0635ad5e0fdab98a9cbd75ffdd2ee5d5e5b6944`) supplied only the `youtube_id` column. The 20-archive path list SHA-256 is `7c75bab47da18ba747e8bdd826bec9139672336fd3431caa71ff563473080e77`. Source IDs were sorted by `SHA256("v6-h265-holdout-20260928\0" + ID)`, then ID. No labels, model predictions, codec outcomes or video frames were inspected during ranking.

| ID-only audit | Count |
|---|---:|
| Unique official validation IDs | 19,906 |
| Historical V1/V2 inventory IDs | 28,625 |
| Historical inventory / official overlap | 0 |
| FIT/CAL/DEV IDs excluded | 800 (official overlap 0) |
| Previously evaluated V2 holdout IDs excluded | 1,000 |
| Previously evaluated V4 holdout IDs excluded | 1,000 |
| Remaining eligible official IDs | 17,906 |
| Hash-ranked candidates locked for byte preflight | 2,000 |

The [candidate plan](../configs/v6_holdout_source_audit/candidate_plan.json) has SHA-256 `4e2f1e79dde04f58ce652fc227541cab446864a5480f818b6b01d710e6078340`; the [ordered candidate IDs](../configs/v6_holdout_source_audit/candidate_ids.txt) have SHA-256 `aac3bf32f0c7f3f8107ffe87e55784bf906bb8bc0abed07f50289521692eb833`. Candidate source fingerprint (sorted-ID SHA-256) is `909f1ba64e0b2f9441b05d84f20aa287be9abf9b7fa97beb99aa749e64bd6141`. The candidate set intersects the V2 and V4 selected holdouts in **zero** source IDs. This is source-ID separation within K400, not an external-domain test; reposted content under another ID remains possible.

## Byte preflight and source lock

Four private Kaggle CPU notebooks, each pinned to preflight code commit `eb19516f9ec4f5835ad276b5853626be8784f7d1`, streamed disjoint archive ranges `0–4`, `5–9`, `10–14`, `15–19`. They read only committed candidate IDs and archive bytes. SHA-256, URL and member count for **all 20 compressed archives** matched the earlier official V2 audit. The four transport tar SHA-256 values and 1,995 retained video files are recorded in [transport_audit.json](../configs/v6_holdout_source_audit/transport_audit.json), SHA-256 `dc0ce866809d7d17c1fbba20986e9338e56478fc1270e152d2b18a3850660aa8`. The 20 [part manifests](../configs/v6_holdout_source_audit/archive_parts/) record per-video bytes and SHA-256; the combiner verified every tar member before extraction.

The rank-ordered byte/decode preflight found **three missing clips** before selecting 1,000; no clip was removed for its class, bitrate or model outcome. Selected video bytes total **1,599,568,270**. [preflight_selection.json](../configs/v6_holdout_source_audit/preflight_selection.json), SHA-256 `258edf02bd203d93828b1d16523159964006245118181b718949ddd0dba53668`, records the exact rank order and failure reasons. Source fingerprint is `269998dbd77c69b5a990f637506d7e1f4f6af4f9e59c38058d000a44535ce918`.

[selected_ids.txt](../configs/v6_holdout_source_audit/selected_ids.txt) has SHA-256 `db5104acb1b00e134ef3700a4aea9b498e4301c89f8733425cc957caf844c69d`; [selected_sources.json](../configs/v6_holdout_source_audit/selected_sources.json) has SHA-256 `3a59114c9be58bd7f1924342579d0ef85e8d28266c7768b723ca689b0440aa43`. Both and the archive/transport audit were committed at **`dd3f5a14708ca37a9db537d17ca23638a4dfc855` before any label was read**. This selected sample intersects the 800 development, 1,000 V2 holdout, 1,000 V4 holdout and 28,625 historical inventory source IDs in **zero** IDs.

Only after that commit did `ops.lock_v6_holdout index` read labels and class mappings. [index.json](../configs/v6_holdout_source_audit/index.json), SHA-256 `37d7ff5d0763b00f2e335e84012611345438d0ade3ffb216d6ada46542678ce3`, contains exactly the 1,000 locked video paths, labels and hashes. The next step is to commit this index and document before any holdout analyzer run. `ops/paper_holdout_v6.py` then runs `primary`, `mc3` and `merge` once. Its `--prereg-commit` argument is the full commit containing the finalized index, freeze manifest, split document and code; both 500-source shards must be present. Until these measurements finish, V6 holdout BD-rate and gate are **CHƯA ĐO**.
