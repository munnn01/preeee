# V11 H.265 CAL artifacts

[Báo cáo](../../docs/RESULTS_V11_SPATIAL_CAL.md): **GO ở bước chọn CAL**, 29/36 cấu hình hợp lệ; V11 `mc3_18`, DEV, CI và holdout mới **CHƯA ĐO**. Đây là phát triển trên CAL được dùng lại, không phải xác nhận độc lập.

## Kết quả và hash

| Artifact | SHA-256 |
|---|---|
| [Frozen calibration](../../configs/v11_spatial/frozen_calibration.json) | `280c926a65458a00b192ed1cd0a44e6b341ac6a4f049c96852d5b0e15a410a0e` |
| [Diagnostics](diagnostics.json) | `c7fbea92d09521bcb2df854a0f02b5713513430df06aefeb63cea361b058a247` |
| [Archive inventory](archive_inventory.json) | `464634a0cfbb1429f6247bdd1d845b7338725e3ed4e81c35e3b8f217346aa07a` |

Mỗi JSON có sidecar `.sha256`. Inventory giữ hash và kích thước của archive, từng thành viên, cùng URL notebook. Archive giữ nguyên byte tải từ Kaggle, gồm `shard_records.jsonl`, `manifest.json`, `manifest.sha256`, `run.log`; không chứa video nguồn hoặc credential.

| Shard | Notebook Kaggle | Archive SHA-256 |
|---:|---|---|
| 0 | [shungg05](https://www.kaggle.com/code/shungg05/v11-spatial-cal-s0-a0a112e) | `769c14517625994710f31725bbe91e9b9a6d0f1e1fdc3e3958e32df621d0fef3` |
| 1 | [dieulinhh](https://www.kaggle.com/code/dieulinhh/v11-spatial-cal-s1-a0a112e) | `eeee13999a747593f69aeee2564a2c4802bff9936a1bb54b44726c8d55cebb22` |
| 2 | [huolgggnuyen](https://www.kaggle.com/code/huolgggnuyen/v11-spatial-cal-s2-a0a112e) | `490bbf4e8d5cafeadbd094518d20ec5282a75ed3585abcaa6f5c7b8b23e418d6` |
| 3 | [baooo25r](https://www.kaggle.com/code/baooo25r/v11-spatial-cal-s3-a0a112e) | `4a9113fd5d412352266089e59c18b7629bd8ed8fb7b0a820e4bfeaa241e302b1` |

Runner `ops.v11_spatial_cal.load_shards` đã xác minh đủ 50 nguồn/shard, không trùng nguồn, hash nguồn/input/protocol/code và mọi bpp tham chiếu trong dung sai `1e−9`. Tổng 1.989 trial encode/decode là số stream identity/V2/V6 khác nhau trên 200×5 cặp nguồn–QP. Worker không dựng analyzer hoặc đọc nhãn; hai-primary correctness được ghép từ cache CAL đã khóa khi calibrate trên local. Không chạy `mc3_18` hoặc bootstrap CAL.

## Provenance

- Preregistration commit: `00951bd52efeb3c64feb62254cef2aa484431e60`, SHA-256 `2dda253a7297566bc97ac8f7800f4e6d20c49d8ad8e51c30a6147a7bfb5328c8`.
- Code commit: `a0a112e6d2525e2743470bca8927115707f87e26`, code fingerprint `53c031bffe2f987ab3a9d8b0dcd89462664d73b140f72b643c61405d6c7b7afe`.
- Plan SHA-256: `bb4b9aa245ff2d8b5f92cb1a45dedb65adfc8a664543878bb7b9cdb1486b421e`.
- CAL input SHA-256: `db9fd6eef315657b33f9e0d557260c7af2a89857633193e6d41c83b056a7983d`.
- CAL source fingerprint: `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`; từng source byte SHA-256 có trong input và record.
- CAL xác định, bootstrap không áp dụng; quy tắc DEV kế tiếp là seed `20261008`, 2.000 draw theo source video, ghép cặp QP/arm/analyzer, CI 95%.

Policy đã chọn `tau=0`, `slack=0.05`, `qp_mode=all` phải được commit trước khi chuẩn bị DEV. Không hiệu chỉnh lại bằng kết quả `mc3_18` hoặc holdout đã xem. [Preregistration đã khóa](../../docs/PREREGISTRATION_V11_112_RESIDUAL.md) quy định trình tự và điều kiện dừng.
