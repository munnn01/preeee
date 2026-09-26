# V2-C replication on the previously inspected 1,000-video TEST set

The frozen V2-C selector chose streams using `r2plus1d_18` and `r3d_18` only. `mc3_18` evaluated the chosen and identity streams afterward. The 1,000 source videos have fingerprint `aae3888f3ae34d08` and are the **same TEST set seen in V1/V2**. This package tests analyzer transfer on old data; it is **not** an independent data holdout.

Both codecs have two complete 500-video shards. `ops.paper_heldout_mc3 merge` was rerun with 2,000 paired source-video bootstrap draws and seed `20260924`. The regenerated JSONs match the historical merged JSONs **byte-for-byte**: H.264 source SHA-256 `0071b2dc7ce29fdf5ac12f69d086c52914503fde5224756342cac3a2199a37e2`; H.265 source SHA-256 `c7de7801aee2ebd8dd48254fd5dd4a9346921a1c5b55a7e2e979b79`. No shard BD-rates were averaged.

| Codec | Analyzer | BD-rate Top-1 | 95% source-video bootstrap CI |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | −22.01% | [−23.85%, −20.24%] |
| H.264 | `r3d_18` | −14.47% | [−15.69%, −13.21%] |
| H.264 | `mc3_18` | −3.88% | [−6.02%, −1.62%] |
| H.265 | `r2plus1d_18` | −14.03% | [−15.39%, −12.77%] |
| H.265 | `r3d_18` | −8.72% | [−9.62%, −7.82%] |
| H.265 | `mc3_18` | −2.10% | [−3.68%, −0.62%] |

The original gate still **fails**: no codec has BD-rate Top-1 strictly below −15% on both development analyzers. `mc3_18` has a smaller saving than either development analyzer. Its evaluation does not repair the absence of an independent source holdout.

`h264_result.json` and `h265_result.json` contain the mc3 curves, metrics, intervals, seed, source code commit, config/index SHA-256, and raw-shard hashes. `combined_old_test.json` references all six analyzer–codec results, including the committed V2 aggregates in `results/dual_codec_search_v2_confirm_1000/`. The four original `manifest.json` and `shard_records.jsonl` files are under `raw/` so the mc3 values can be recomputed. `SHA256SUMS.txt` lists every packaged file's SHA-256. The historical source execution commit was `e103771fd6729d29208517c688af96c2c58c0506`; the packaging code commit is recorded in each JSON.
