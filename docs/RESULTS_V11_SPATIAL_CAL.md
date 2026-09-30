# V11 H.265: kết quả CAL và đánh giá giới hạn

## Kết luận

**GO ở bước chọn policy trên CAL: 29/36 cấu hình hợp lệ.** Policy được chọn là `tau=0`, `slack=0.05`, `qp_mode=all`; trạng thái máy đọc được là `FREEZE_BEFORE_DEV`. Hai analyzer chính đạt BD-rate Top-1 so với identity **−13,92%** và **−13,81%**. Đây là kết quả phát triển trên 200 nguồn CAL đã dùng trước đây, **không phải xác nhận trên holdout mới**. Nguồn: [toàn bộ lưới và policy chọn](../configs/v11_spatial/frozen_calibration.json).

**Mục tiêu đầy đủ chưa được xác nhận:** V11 `mc3_18`, DEV, CI 95% và holdout mới đều **CHƯA ĐO**. Gate nghiên cứu gốc **<−15% trên cả hai analyzer chính** được giữ nguyên; hai point estimate CAL hiện tại chưa đạt ngưỡng này. GO trên CAL chỉ cho phép freeze rồi chuyển sang phép đo DEV đã preregister.

## Kiểm tra tính xác thực

Bốn job Kaggle đã hoàn tất. Mỗi shard có 50 nguồn, tổng cộng 200 nguồn và đủ năm QP `30,35,40,45,50`, H.265/libx265 preset medium. Đã kiểm tra đường dẫn và loại thành viên TAR trước khi đọc, SHA-256 archive/manifest/record, ID và byte hash nguồn, provenance và bitrate đối chiếu cache khóa. Cả bốn shard hợp lệ; bpp mã hóa lại khớp tham chiếu trong dung sai đã khóa `1e−9`. Chỉ các stream khác nhau trong identity/V2-C/V6 được encode/decode: 495, 492, 504 và 498 trial, tổng **1.989 trial**. [Inventory gốc](../results/v11_spatial_cal/archive_inventory.json) và [manifest trong kết quả gộp](../configs/v11_spatial/frozen_calibration.json) giữ bằng chứng.

Worker CAL chỉ đo pixel/proxy, không dựng analyzer và không đọc nhãn. Top-1 của hai analyzer chính được ghép từ correctness lịch sử đã khóa trên chính nguồn CAL và candidate tương ứng; đây **không phải lượt suy luận mới của ba analyzer**. `mc3_18` không tham gia CAL. Những kết quả lịch sử của `mc3_18` đã ảnh hưởng đến giả thuyết nghiên cứu, nên không được gọi nó là kiến trúc chưa từng quan sát.

## Kết quả trên cùng 200 nguồn CAL

Tất cả các giá trị dưới đây so với **identity trên cùng nguồn**. BD-accuracy và same-QP gap được đổi từ tỷ lệ sang điểm phần trăm; BD-rate âm hơn là tốt hơn. Không có bootstrap CAL trong giao thức này, do đó **CI CAL: CHƯA ĐO**. Nguồn: `v6_baseline` và hàng `grid` có `policy == selected_policy` trong [JSON gộp](../configs/v11_spatial/frozen_calibration.json).

| Policy | Analyzer | BD-rate Top-1 | BD-accuracy (pp) | Worst same-QP Top-1 gap (pp) |
|---|---|---:|---:|---:|
| V6 | `r2plus1d_18` | −14,05% | +10,78 | +2,00 |
| V11 | `r2plus1d_18` | **−13,92%** | +10,69 | +2,00 |
| V6 | `r3d_18` | −14,49% | +10,15 | +0,50 |
| V11 | `r3d_18` | **−13,81%** | +9,56 | +0,50 |

Cả hai analyzer qua các điều kiện CAL: BD-rate <−10%, BD-accuracy >0, worst gap ≥−1,00 pp, BD-rate không kém V6 quá 1,00 pp; mean D112 giảm quá `1e−6`. Không so bảng này với số V6/V2 trên một tập khác để quy kết cải thiện.

Phép so sánh **trực tiếp V11 với V6**, tính lại trên hai curve cùng CAL, cho thấy một chi phí nhỏ trên hai analyzer chính. Không lấy hiệu hai BD-rate so với identity làm BD-rate trực tiếp. Nguồn: [diagnostics.json](../results/v11_spatial_cal/diagnostics.json), `V11_vs_V6_direct`.

| Analyzer | BD-rate trực tiếp V11/V6 | BD-accuracy trực tiếp (pp) | Worst same-QP gap V11−V6 (pp) |
|---|---:|---:|---:|
| `r2plus1d_18` | +0,15% | −0,09 | 0,00 |
| `r3d_18` | +0,77% | −0,60 | −1,00 |

Các số trực tiếp chỉ mô tả CAL sau khi đã chọn policy, không có CI và không chứng minh độ tương đương thống kê.

## Policy đã chọn thực sự thay đổi gì

V11 mặc định giữ lựa chọn V6. Chỉ đổi sang stream V2-C khi khác stream V6, `D112(V6)−D112(V2)>0`, bitrate V2 không vượt `1.05 × bitrate V6` và không vượt identity. QP cho phép gồm cả năm mức. Đây là lựa chọn đúng lưới đã khóa, không thêm ngoại lệ theo video hay ngưỡng hậu nghiệm. [Preregistration](PREREGISTRATION_V11_112_RESIDUAL.md) mô tả D112 trên tensor RGB đã resize/normalize ở lưới 112 của analyzer.

Mean D112 giảm **0,393285 → 0,386632**, tức **1,69% tương đối** so với V6. Đây là cải thiện proxy, **không phải mức cải thiện Top-1 hoặc BD-rate của `mc3_18`**. Có 96 lần đổi trong 1.000 cặp nguồn–QP, tác động đến 78 nguồn; 93 lần đổi tới identity. Nguồn: [diagnostics.json](../results/v11_spatial_cal/diagnostics.json) và hàng policy chọn trong [JSON gộp](../configs/v11_spatial/frozen_calibration.json).

| QP | Số lần V6 → V2-C |
|---:|---:|
| 30 | 1 |
| 35 | 3 |
| 40 | 8 |
| 45 | 23 |
| 50 | 61 |

**84/96 lần đổi (87,50%) nằm tại QP 45–50.** Chỉ 12 lần đổi ở QP 30–40. Trên những lần đổi, `r2plus1d_18` lấy lại một dự đoán đúng ở QP 45; `r3d_18` mất một ở QP 35 và hai ở QP 40. Điều này giải thích vì sao vẫn giữ được rate gate chính nhưng chất lượng trực tiếp của `r3d_18` thấp hơn V6. Số đếm ghép cặp ở `primary_correctness_changes_on_switches` trong [diagnostics.json](../results/v11_spatial_cal/diagnostics.json).

## Đánh giá khả thi và bước tiếp theo

- **Có cơ sở tiếp tục đo DEV:** policy đã qua điều kiện chọn CAL và còn giữ mức tiết kiệm bitrate >10% trên hai analyzer chính. V11 tránh sự sụt giảm lớn của spatial gate V10 bằng cách bắt đầu từ V6 và chỉ sửa những stream V2 có proxy tốt hơn.
- **Bằng chứng bảo vệ chuyển giao còn yếu:** D112 chỉ giảm 1,69%, hầu hết thay đổi ở QP cao; proxy tốt hơn chưa được kiểm chứng là dự báo đúng việc lấy lại dự đoán của `mc3_18`. Đặc biệt, phần lớn lựa chọn ở QP 30–40 vẫn giữ V6. Đây là lý do phải đo, không phải căn cứ dự đoán một con số `mc3_18`.
- **CAL đã được tái sử dụng và dùng để chọn trong 36 cấu hình:** các point estimate có thể lạc quan; không được dùng chúng làm kết luận tổng quát hóa hay kết quả tạp chí xác nhận. Full selector runtime/peak memory của V11: **CHƯA ĐO**; 1.989 trial CAL không phải số đo overhead triển khai đầy đủ.

Theo giao thức, commit policy và kết quả CAL trước khi chuẩn bị DEV. Giữ nguyên policy này, ghi toàn bộ lựa chọn stream trước khi đọc nhãn hoặc dựng ba analyzer, rồi đo một lượt trên 200 nguồn DEV với các arm identity, area112, V2-C, V6, V11. Gộp curve đủ nguồn và năm QP; bootstrap ghép cặp **2.000 draw theo video nguồn**, seed **20261008**, giữ tất cả QP/arm/analyzer trong mỗi draw và yêu cầu ít nhất 1.900 draw hợp lệ cho từng metric.

GO DEV cần cả hai analyzer chính <−10%; `mc3_18` <0 và CI trên ≤+1%; BD-accuracy >0 cùng worst gap ≥−1,00 pp trên cả ba. Nếu trượt, ghi NO-GO theo đúng ngưỡng. Gate gốc <−15% vẫn báo riêng. Holdout nguồn mới chỉ được mở dưới một preregistration riêng sau khi freeze; kết quả holdout đã xem không được dùng để chọn ngưỡng V11.

## Provenance và SHA-256

- Preregistration commit: `00951bd52efeb3c64feb62254cef2aa484431e60`.
- Preregistration Git-blob SHA-256: `2dda253a7297566bc97ac8f7800f4e6d20c49d8ad8e51c30a6147a7bfb5328c8`.
- Code commit chạy CAL: `a0a112e6d2525e2743470bca8927115707f87e26`.
- Code fingerprint: `53c031bffe2f987ab3a9d8b0dcd89462664d73b140f72b643c61405d6c7b7afe`.
- Plan Git-blob SHA-256: `bb4b9aa245ff2d8b5f92cb1a45dedb65adfc8a664543878bb7b9cdb1486b421e`.
- CAL input Git-blob SHA-256: `db9fd6eef315657b33f9e0d557260c7af2a89857633193e6d41c83b056a7983d`.
- CAL source-ID fingerprint: `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`; SHA-256 từng video nguồn nằm trong input đã khóa và raw record.
- Frozen result SHA-256: `280c926a65458a00b192ed1cd0a44e6b341ac6a4f049c96852d5b0e15a410a0e`.
- Diagnostics SHA-256: `c7fbea92d09521bcb2df854a0f02b5713513430df06aefeb63cea361b058a247`.
- Archive inventory SHA-256: `464634a0cfbb1429f6247bdd1d845b7338725e3ed4e81c35e3b8f217346aa07a`.

CAL là phép tính xác định, **không chạy bootstrap**. Seed/draw/unit trong provenance có hậu tố `if_dev`, chỉ là quy tắc cho bước DEV, không phải CI đã đo. Môi trường shard được ghi trong manifest: Python 3.12.13, Torch 2.10.0+cpu, OpenCV 4.13.0, NumPy 2.0.2 và FFmpeg 4.4.2. [Gói kết quả và archive nguyên bản](../results/v11_spatial_cal/README.md) cho phép kiểm toán mọi số trên.
