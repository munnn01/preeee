# V10 H.265 spatial gate CAL artifacts

[Báo cáo](../../docs/RESULTS_V10_SPATIAL_GATE_CAL.md) ghi kết luận **NO-GO**. [Kết quả gộp](../../configs/v10_spatial/frozen_calibration.json) có sidecar SHA-256 trong cùng thư mục `configs/v10_spatial`; SHA-256 của JSON là `b074fe1f01b60f6103223e55c1e1afb0ab8ddfc8208dd5ac6da856c3b63d48d8`. [Inventory](archive_inventory.json) có hash byte của archive và từng thành viên; [sidecar](archive_inventory.sha256) kiểm tra inventory.

| Shard | Kaggle notebook | Archive SHA-256 |
|---:|---|---|
| 0 | [shungg05](https://www.kaggle.com/code/shungg05/v10-spatial-cal-s0-df21c48) | `206b916b6302d131b89ec162a42c61abac7997b5358c3be08a2bfdb03d90164e` |
| 1 | [dieulinhh](https://www.kaggle.com/code/dieulinhh/v10-spatial-cal-s1-df21c48) | `750da9a68c4315c64fe091893b0516182825612091196c7bbf9366b31d7026c0` |
| 2 | [huolgggnuyen](https://www.kaggle.com/code/huolgggnuyen/v10-spatial-cal-s2-df21c48) | `3ecfc18cf281c5e7795adba4b3d2fc089a693f3ad9a74eeaff9ea2e6064a24a8` |
| 3 | [baooo25r](https://www.kaggle.com/code/baooo25r/v10-spatial-cal-s3-df21c48) | `16b89fe1c9db3de3fd3ebc14fc5da119b506e387341c52b717e866fa5aa15006` |

Mỗi archive giữ `proxy_records.jsonl`, `shard_records.jsonl`, `manifest.json`, `manifest.sha256` và log chạy; không chứa video nguồn hoặc credential. Runner `load_shards` đã xác minh đủ 50 nguồn/shard, 1.500 trial/shard, SHA-256 của record và video, input manifest, codec bpp và provenance. 200 nguồn CAL là dữ liệu phát triển được dùng lại; `mc3_18`, DEV và holdout V10: **CHƯA ĐO**.
