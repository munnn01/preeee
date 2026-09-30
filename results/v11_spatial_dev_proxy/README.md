# V11 DEV proxy artifacts

[Báo cáo](../../docs/RESULTS_V11_DEV_PROXY.md) ghi kết quả mô tả không nhãn. [Selection toàn DEV](../../configs/v11_spatial/dev_selection.json), SHA-256 `e0489ac9e39347bc31ac8c57f3bcc71f9f3d72580f3d5d25be8c1266171cab01`, khóa 200×5 lựa chọn trước scoring. V11 DEV BD-rate, CI và `mc3_18`: **CHƯA ĐO** ở bước này.

- [diagnostics.json](diagnostics.json) và sidecar: D112, bpp, số đổi theo QP và transition count; không có Top-1, BD-rate hoặc CI suy đoán.
- [archive_inventory.json](archive_inventory.json) và sidecar: SHA-256 archive nguyên bản, từng thành viên, URL notebook, số nguồn và trial mỗi shard.
- [generator.json](generator.json) và sidecar: hash của script đóng gói/thống kê [package_proxy.py](package_proxy.py). Script ghi thuật toán phân tích mô tả và các đường dẫn đầu vào của lượt này; không sửa policy.
- `archives/v11_dev_proxy_shard{0,1,2,3}.tgz`: archive nguyên bản, gồm manifest, sidecar, record JSONL và log. Không chứa video hoặc credential.

Worker commit `4ec110533b4b9dee64c93699a6ff60b637c9e7b9`; seal/base analysis commit `bdc3e98aed0c566bcaf771139f98ebcd5c420d69`. Preregistration commit `00951bd52efeb3c64feb62254cef2aa484431e60`; policy CAL freeze commit `49fb15f6de86f09c6c0a845098cbbf199c405c03`. Input DEV SHA-256 `2c48519cb06b7b4580302d629aa7267fe0e35e8fc6ca525d18fa39909114eca5`; source fingerprint `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`. Từng source SHA-256 trong input và raw records. Provenance giữ code/preregistration/plan/CAL hash.

Proxy không chạy bootstrap. Bước scoring/merge sau dùng seed `20261008`, 2.000 paired draw theo **source video**, giữ đủ QP/arm/analyzer. [Runbook hai giai đoạn](../../docs/V11_DEV_RUNBOOK.md) yêu cầu commit global selection trước khi gửi notebook scoring. Tập này là DEV được dùng lại, không phải nguồn holdout mới.
