# V6 residual selector: original Kaggle FIT/CAL/DEV output

The private notebook [shungg05/v6-dev-residual-db57f13](https://www.kaggle.com/code/shungg05/v6-dev-residual-db57f13) completed successfully. This folder preserves the original `v6_dev_residual.tgz`, its exact extracted JSON/model bytes, input manifest, run log and Kaggle kernel log. `SHA256SUMS.txt` covers these downloaded files. The `.gitattributes` rule prevents line-ending conversion of the raw evidence.

| Artifact | SHA-256 |
|---|---|
| Original archive | `6a578b4d0f30a9a31f9227bb2e4e7679ef1e850377dc979382130d69fde0af0e` |
| [H.264 JSON](results/h264_result.json) | `67e3f9bb2167e3255ce2ac51d4f8e42a19a81b754f4963ae7af1f3f898257572` |
| [H.265 JSON](results/h265_result.json) | `371d1485edd2848fbc1a652fbd5220bc818514ee1afbad5c5bbea0ac6b88ebb9` |
| Locked DEV cache manifest | `5064f454b3602fe2d7e8c0adaff09c4a990622b836978d8d3c0b7c1a46b8fd9d` |

Preregistration commit: `efdf5e3d7bd0889c6dc09bc05dc12c928ffb1159`; code commit: `db57f13fcc7acd72f5c7f90f316134ebaf1ec48f`. The result JSON records each codec's source fingerprints, frozen V2 risk/policy and cache tree hashes, four fitted event-model hashes, sklearn version, exact CAL grid, policy, curves, choices, bootstrap seed `20260930`, source-video resampling unit and 2,000 draws. Model hashes have been checked against all eight archived `.joblib` files. The `frozen_policy_sha256` fields refer to the archived V2 pilot cache; the repository policy copy has different line endings, as documented in `docs/PREREGISTRATION.md`.

H.264 selected a CAL policy but failed the locked DEV rule. H.265 selected a CAL policy and passed the locked DEV go/no-go. Neither codec has a V6 `mc3_18` or new-holdout result. See [the developmental result report](../../docs/RESULTS_V6_DEV.md) for exact comparisons and limitations.
