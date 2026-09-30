# V11 H.265 — frozen policy assessment on reused DEV

**NO-GO.** Two primary point rates pass −10%, but MC3 fails the preregistered CI upper and same-QP guard. Original two-primary −15% point gate also fails on this reused DEV; new holdout: CHƯA ĐO.

- [Full report](../../docs/RESULTS_V11_DEV.md).
- [Merged result](h265_result.json), SHA-256 `624f889efd3e21cef60cb6390b6a237e25f6b384f6887f0c02e73fe1d8514afe`; five-QP full-source curves, all seven direct comparisons, three analyzers, 2,000 paired source-video draws (seed 20261008), 2,000 valid draws per BD-rate/BD-accuracy.
- [Validation](validation.json): four complete shards, 200 sources, 2493 unique encode/decode trials, matching source/selection/decoded hashes, weights, environment and predictions. [Diagnostics](diagnostics.json) and [guard deficits](guard_deficits.json) are descriptive post-freeze counts/arithmetic; no separate bootstrap and no policy tuning.
- [Archive inventory](archive_inventory.json) records exact archive/member/log/helper SHA-256. `archives/` retains all four original `v11_dev_score_shard*.tgz`; each contains manifest+sidecar, 50 raw records and run log. `kaggle_logs/` preserves original console logs. [Status snapshot](status_snapshot.json) records four COMPLETE statuses; the submission receipt remains unchanged in `../v11_spatial_dev_score_launch/`.
- [Local analysis environment](analysis_environment.json) separates merge Python/NumPy versions from the CUDA workers and records a fingerprint reconstructed from the locked bootstrap seed/expression.
- [Generator](generator.json) binds external review helpers and analysis base commit. Helpers in `review_helpers/` document downloading/safe extraction, validation/merge and descriptive diagnostics. The local review staging directory was `D:/STUDY/LAB/proxy_v3/v11_dev_score_review`; fresh artifacts are required by helpers, and original results must not be overwritten.

Policy freeze `49fb15f6de86f09c6c0a845098cbbf199c405c03`; all 200×5 choices committed before inference at `f67391e22c2d9ec2d7be0d34bf307c7c02b5fd77`. Merge base `91ba5721ad6dc21657bb0e8f675df344b5c6e7ad`; code fingerprint `5eee253b68a62498eeaeb0b10bd8e463e60d9248145273f7f7286f257c0ad07f`. DEV input SHA-256 `2c48519cb06b7b4580302d629aa7267fe0e35e8fc6ca525d18fa39909114eca5`; selection SHA-256 `e0489ac9e39347bc31ac8c57f3bcc71f9f3d72580f3d5d25be8c1266171cab01`; DEV fingerprint `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`. Source bytes are SHA-256 pinned. All metadata is in the JSONs; sidecars bind exact bytes, protected from Git newline conversion by `.gitattributes`.

No TEST/holdout evaluation, threshold change, refit, or metric/bootstrap change. Earlier MC3 outcomes informed the hypothesis, so this is a transfer assessment on reused development sources. Full six-candidate selector runtime, V11 H.264 and fresh holdout remain CHƯA ĐO.

## Reproduce the metrics from validated records

Safely extract only the expected four members of each original archive into four new directories. From a checkout with unchanged locked inputs/worker code, use a fresh output:

```powershell
& 'D:/STUDY/AI/envs/ten_env/python.exe' -B -u -X utf8 -m ops.v11_spatial_dev merge --shard-dir $score0 --shard-dir $score1 --shard-dir $score2 --shard-dir $score3 --out $freshResult
```

The loader validates all partitions/manifests/raw records against the globally committed selection, then merges sources before BD calculations. Analysis commit provenance will refer to the replay checkout; compare numeric curves/metrics/intervals with the original JSON rather than expecting a different checkout's entire JSON hash to match. Unit resampling stays source video across QPs/arms/analyzers. The existing preregistration and historical result files stay immutable.
