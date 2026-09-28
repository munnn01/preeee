# V5 agreement guard: original Kaggle CAL output

The private Kaggle notebook `shungg05/v5-dev-agreement-12a37e4` completed. This folder preserves the downloaded archive (`v5_dev_agreement.tgz`) and its exact metric JSON, sidecars, input manifest and run log. The JSON files have not been reformatted. `SHA256SUMS.txt` covers the downloaded files. The `.gitattributes` rule preserves their raw bytes in Git.

| Item | SHA-256 |
|---|---|
| Downloaded archive | `ce75ea8d5cfdfaa4ba7f9774987773283361cc01a5d6131ad019d2646d469ed8` |
| [H.264 result](results/h264_result.json) | `98b1275b2765565ee5404ccd7e5de76ff9cb4d45662eec16d5a0ef087df50576` |
| [H.265 result](results/h265_result.json) | `632e9996296f23086b980e62372fb5957d8c8dd938f4eb890b50ecd916a66769` |
| DEV cache manifest | `5064f454b3602fe2d7e8c0adaff09c4a990622b836978d8d3c0b7c1a46b8fd9d` |

Preregistration commit: `bca2f7ce26c8b741c124d878a714495b4897c789`. Analysis code commit: `12a37e4080413dc4029e957ff9d93ece39518761`. Frozen V4 manifest SHA-256: `c59d6e4fa4e7837e9f86cd418af0b1c1afcd75adae490ae4e8b3bc3eed45f06f`. Original V2 cache archive SHA-256: `fba0149d3320398c92ecfd51a194e365b4b04832f8d4334110be19569fc15c17`. The result JSON contains per-codec model and cache hashes and FIT/CAL/DEV source fingerprints. The `frozen_policy_sha256` fields refer to the **archived V2 pilot cache files verified by this run**, not to any current working-tree policy file.

Both codecs have 81 CAL configurations, zero feasible configurations, `selected_policy: null`, and `dev: null`. Hence there is **no V5 policy**, no DEV bootstrap/CI, and no new holdout or `mc3_18` result. The result files record the planned source-video bootstrap unit, seed `20260929` and 2,000 draws; the stopping rule prevented DEV bootstrap from running.

See [the interpretation and full CAL table](../../docs/RESULTS_V5_DEV.md).
