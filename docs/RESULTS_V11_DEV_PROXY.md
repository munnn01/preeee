# V11 DEV proxy: kết quả và giới hạn

## Kết luận

**Bốn shard hoàn tất và hợp lệ**, tổng 200 video nguồn DEV, 1.000 cặp nguồn–QP và 1.969 trial encode/decode. Toàn bộ lựa chọn stream đã được ghi vào [manifest toàn DEV](../configs/v11_spatial/dev_selection.json) bằng đúng policy CAL `tau=0, slack=0.05, qp_mode=all`, không chọn lại ngưỡng. SHA-256 selection: `e0489ac9e39347bc31ac8c57f3bcc71f9f3d72580f3d5d25be8c1266171cab01`.

Đây là **đo proxy không nhãn**, chưa có suy luận analyzer. **V11 DEV BD-rate, Top-1, BD-accuracy, worst same-QP gap, CI 95% và `mc3_18`: CHƯA ĐO.** Gate kỹ thuật đầy đủ và gate gốc <−15% chưa được đánh giá ở bước này. Kết quả không phải holdout độc lập.

## Kiểm toán

Đã tải archive nguyên bản từ bốn notebook private, kiểm tra đường dẫn/loại/kích thước thành viên TAR trước khi đọc, SHA-256 archive/manifest/record, đầy đủ 50 nguồn mỗi shard và không trùng nguồn. Runner đã xác minh source ID/byte hash, input SHA, code fingerprint, code commit và đủ năm QP `30,35,40,45,50`; bpp từng stream khớp tham chiếu trong dung sai đã khóa `1e−9`. Số trial các shard là 492, 480, 505, 492. Nguồn: [archive inventory](../results/v11_spatial_dev_proxy/archive_inventory.json) và các manifest nằm trong [selection](../configs/v11_spatial/dev_selection.json).

Worker chỉ đo các stream khác nhau trong identity/V2-C/V6 cho mỗi source–QP. Không dựng analyzer hoặc đọc label/correctness. Việc khóa toàn bộ 200×5 lựa chọn hoàn tất trước lượt scoring; giữ nguyên policy V11 và các policy/model V2/V6. Dữ liệu DEV này đã được dùng trong phát triển trước đây, và lịch sử `mc3_18` đã ảnh hưởng đến giả thuyết; không gọi nó là kiến trúc chưa từng quan sát.

## Thay đổi đo được

Nguồn toàn bộ số dưới đây: [diagnostics.json](../results/v11_spatial_dev_proxy/diagnostics.json), tính từ selection đã khóa. D112 là proxy khoảng cách gradient/Laplacian trên lưới analyzer 112, không phải accuracy. Mean bpp là bitrate chuẩn hóa bình quân; **chênh bpp cùng QP không phải BD-rate**, vì chưa có quality/Top-1.

| QP | Số đổi V6 → V2-C | Mean D112 V6 | Mean D112 V11 | D112 giảm tương đối | Mean bpp V11/V6 tăng |
|---:|---:|---:|---:|---:|---:|
| 30 | 0 | 0,185561 | 0,185561 | 0,00% | 0,00% |
| 35 | 6 | 0,267839 | 0,266504 | 0,50% | 0,04% |
| 40 | 9 | 0,361032 | 0,358294 | 0,76% | 0,10% |
| 45 | 28 | 0,485117 | 0,475422 | 2,00% | 0,34% |
| 50 | 52 | 0,651414 | 0,635185 | 2,49% | 0,40% |

Trên tất cả 1.000 cặp nguồn–QP, mean D112 giảm **0,390193 → 0,384193**, tương đương **1,54%**; mean bpp tăng **0,12%**. Cụ thể, D112 reduction relative = `100 × (1 − mean_D112_V11 / mean_D112_V6)`; bpp delta = `100 × (mean_bpp_V11 / mean_bpp_V6 − 1)`, mỗi source–QP có cùng trọng số.

V11 đổi 95/1.000 cặp, tác động đến 71 nguồn. 88 lần đổi sang identity; 7 lần đổi tới candidate khác trong bộ stream cũ. Không thêm bộ lọc hay biến đổi màu mới. **80/95 lần đổi (84,21%) nằm tại QP 45–50**. Ở QP 30–40, chỉ 15/600 cặp thay đổi: **97,50% vẫn giữ V6**. Số đếm nằm trong `transitions` và `by_qp` của [diagnostics](../results/v11_spatial_dev_proxy/diagnostics.json).

## Đánh giá khả thi

- **Hành vi proxy ổn định so với CAL:** CAL trước đó giảm D112 1,69%, DEV cố định giảm 1,54%; chi phí bpp trung bình cùng QP trên DEV nhỏ. Đây là thống kê mô tả, không có kiểm định tương đương và không chứng minh giữ được BD-rate hai analyzer chính. [Kết quả CAL](RESULTS_V11_SPATIAL_CAL.md) truy về JSON CAL riêng.
- **Khả năng sửa điểm yếu ở QP thấp còn hạn chế:** policy không thay lựa chọn nào ở QP 30 và chỉ thay ít ở QP 35/40. Nếu mất chi tiết trong các lựa chọn giữ V6 là nguyên nhân của lỗi chuyển giao, cơ chế sửa hiện tại tác động đến rất ít cặp này. Đây là suy luận từ phân bố lựa chọn, không phải kết quả `mc3_18`.
- **Chưa có bằng chứng đạt mục tiêu chuyển giao:** chưa biết proxy giảm có giúp lấy lại dự đoán đúng hay không. D112 tốt hơn không đảm bảo Top-1 tốt hơn; không dự đoán hoặc gán một con số BD-rate cho `mc3_18`.
- **Không tinh chỉnh lại theo DEV proxy:** policy đã freeze trên CAL. Giữ nguyên lựa chọn, đo một lượt đã preregister trên DEV. Chi phí toàn bộ selector và peak memory vẫn CHƯA ĐO; trial ở đây chỉ là đo proxy, không phải phép đo runtime đầy đủ.

## Bước chấm tiếp theo

Commit selection và raw package trước khi scoring. Sau đó triển khai bốn shard với năm arm **identity, area112, V2-C, V6, V11**, cả ba analyzer đóng băng. Scoring chỉ tiêu thụ manifest đã commit; các stream proxy phải tái tạo đúng bpp và decoded SHA-256. Không chọn stream bằng nhãn hay kết quả mới.

Sau khi đủ bốn shard scoring, gộp curve đủ 200 nguồn rồi bootstrap **2.000 draw theo source video**, ghép cặp tất cả QP/arm/analyzer, seed **20261008**, CI 95%. GO DEV cần hai analyzer chính <−10%; `mc3_18` <0 và CI trên ≤+1%; cả ba BD-accuracy >0, worst same-QP gap ≥−1,00 pp; ít nhất 1.900 draw hợp lệ cho mỗi metric/analyzer. Gate gốc <−15% giữ nguyên và được báo riêng trên DEV đã dùng lại. Holdout mới cần preregistration riêng, chưa được chạy trong lượt này.

## Provenance

- Worker commit: `4ec110533b4b9dee64c93699a6ff60b637c9e7b9`.
- Selection generator/base analysis commit: `bdc3e98aed0c566bcaf771139f98ebcd5c420d69`; code fingerprint không đổi: `5eee253b68a62498eeaeb0b10bd8e463e60d9248145273f7f7286f257c0ad07f`.
- Preregistration commit: `00951bd52efeb3c64feb62254cef2aa484431e60`, SHA-256 `2dda253a7297566bc97ac8f7800f4e6d20c49d8ad8e51c30a6147a7bfb5328c8`.
- CAL freeze commit: `49fb15f6de86f09c6c0a845098cbbf199c405c03`, result SHA-256 `280c926a65458a00b192ed1cd0a44e6b341ac6a4f049c96852d5b0e15a410a0e`.
- Plan SHA-256: `bb4b9aa245ff2d8b5f92cb1a45dedb65adfc8a664543878bb7b9cdb1486b421e`.
- DEV input SHA-256: `2c48519cb06b7b4580302d629aa7267fe0e35e8fc6ca525d18fa39909114eca5`.
- DEV source fingerprint: `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`; từng source byte SHA-256 nằm trong input, selection và raw record.
- Bootstrap thực tế ở bước proxy: **0 draw**; 2.000 draw trong provenance là kế hoạch cho merge score, không phải CI đã có.

[Gói archive, sidecar, diagnostic và generator hash](../results/v11_spatial_dev_proxy/README.md) giữ đầy đủ bằng chứng. Không thay `src/metrics/bd_rate.py` hoặc logic bootstrap, không xóa/ghi đè kết quả cũ.
