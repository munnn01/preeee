# V6 H.265 holdout: source audit status

**Status: only the metadata-only candidate plan is fixed. The 1,000-video source list, byte hashes, label index and all analyzer outcomes are CHƯA CHỐT/CHƯA ĐO.** The new [preregistration](PREREGISTRATION_V6_HOLDOUT.md) was committed at `385674ddf93d477d78f0b6b1b4abdff667eee7e5`, before this candidate ranking. The H.265 V6 freeze and audit code were committed at `67067adefeaddda326c9f9c3f6c7560acbc79a9b` before ranking.

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

The next permitted step is `python -m ops.prepare_v6_holdout` with the same annotation, archive list, two historical inventories, FIT manifest and output directory, plus `--download`. It verifies the committed candidate plan before streaming the official archives, checks archive hashes via the two-phase lock, and selects the first 1,000 decodable candidates in rank order. Then `python -m ops.lock_v6_holdout ids` must write `selected_ids.txt` and `selected_sources.json`, which must be committed **before** `python -m ops.lock_v6_holdout index` reads labels. After committing the index and this document's final fingerprints, `ops/paper_holdout_v6.py` can run its `primary`, `mc3` and `merge` commands once. The `--prereg-commit` argument to that runner is the full commit containing the finalized index, freeze manifest, split document and code. Both 500-source shards must be present for each stage. Until these steps finish, the V6 holdout result is **CHƯA ĐO**.
