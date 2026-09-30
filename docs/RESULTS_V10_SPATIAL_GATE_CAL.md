# V10 spatial gate: kết quả CAL H.265

**Kết luận: NO-GO.** Bốn shard Kaggle đã hoàn tất trên 200 video CAL Kinetics-400 đã dùng trong phát triển. Sau khi xác minh archive, manifest và hash, **0/81** cấu hình trong lưới đã khóa đạt điều kiện chọn trên hai analyzer chính. Theo [preregistration đã khóa](PREREGISTRATION_V10_SPATIAL_GATE.md), không chọn policy V10 và dừng trước DEV. `mc3_18`, V10 DEV và holdout mới: **CHƯA ĐO**. Đây không phải một kết quả xác nhận độc lập.

## Dữ liệu và kiểm toán

- Mốc preregistration: `83e4e0209acf7d3994751522e354693e6b698787`; commit chạy Kaggle: `df21c483602573b7cfc989725c1292b04a60533e`.
- Manifest đầu vào SHA-256 `db9fd6eef315657b33f9e0d557260c7af2a89857633193e6d41c83b056a7983d`; fingerprint 200 ID nguồn CAL `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`.
- Bốn shard, mỗi shard 50 nguồn và 1.500 lượt encode/decode H.265; tổng cộng **6.000 lượt** cho sáu candidate × năm QP × 200 nguồn. Mọi bpp mã hóa lại được kiểm tra với cache đã khóa; `load_shards` xác minh ID, SHA-256 video, record, manifest, số nguồn và provenance.
- [JSON CAL đã khóa](../configs/v10_spatial/frozen_calibration.json) có SHA-256 `b074fe1f01b60f6103223e55c1e1afb0ab8ddfc8208dd5ac6da856c3b63d48d8`. [Sidecar](../configs/v10_spatial/frozen_calibration.sha256) và [inventory](../results/v10_spatial_cal/archive_inventory.json) cho phép kiểm tra byte; bốn archive gốc được giữ trong [gói kết quả](../results/v10_spatial_cal/README.md).
- CAL proxy chỉ đọc pixel và bitrate, không tạo analyzer hoặc xem nhãn. Lúc gộp, runner dùng **correctness lịch sử của hai analyzer chính** từ cache CAL đã khóa để tính lưới. Không có dữ liệu `mc3_18` trong bước chọn. Tham số bootstrap 2.000 lần, seed `20261007`, đơn vị source video đã được preregister cho DEV; **không có CI V10** vì gate CAL đã dừng trước DEV.

## Gate và số đo

Gate CAL yêu cầu đồng thời trên cả `r2plus1d_18` và `r3d_18`: BD-rate Top-1 < −10%, BD-accuracy > 0, và worst same-QP Top-1 gap ≥ −1,00 điểm %. Các giá trị dưới đây lấy trực tiếp từ `baselines` và `grid` trong JSON CAL; dòng “gần nhất” là chẩn đoán hậu nghiệm, **không phải policy được chọn**.

| Arm trên đúng 200 CAL | BD-rate `r2plus1d_18` | BD-rate `r3d_18` | Trạng thái |
|---|---:|---:|---|
| V2-C so với identity | −13,27% | −9,28% | R3D không qua −10% |
| V6 so với identity | −14,05% | −14,49% | Baseline lịch sử; không phải cấu hình V10 |
| Cấu hình V10 có worst-primary BD-rate thấp nhất trong lưới | −6,15% | −3,97% | Không qua rate gate; không được chọn |

**0/81** cấu hình V10 qua rate gate của cả hai analyzer; **81/81** qua riêng điều kiện BD-accuracy và **81/81** qua riêng guard same-QP. Cấu hình V10 gần nhất dùng quantile phức tạp `0,90`, `tau=0,10`, minimum saving `0,05`, spatial weight `0,5`; BD-accuracy là +3,03 và +1,85 điểm %, worst same-QP gap là +0,50 và 0,00 điểm %. Dù vậy rate gate vẫn trượt rõ ràng. Khoảng BD-rate của toàn lưới là [−6,15%; −0,24%] trên `r2plus1d_18` và [−3,97%; −0,18%] trên `r3d_18`.

## Chẩn đoán rate–spatial

So sánh ghép cặp `area112` với `identity128` trên mỗi QP trong JSON CAL:

| QP | Tiết kiệm bitrate trung vị của `area112` | Spatial excess trung vị | Top-1 gap `area112−identity` R2+1D / R3D |
|---:|---:|---:|---:|
| 30 | 19,45% | 0,238 | −7,0 / −2,5 điểm % |
| 35 | 14,31% | 0,218 | −4,0 / +2,0 điểm % |
| 40 | 9,28% | 0,177 | −13,5 / −6,0 điểm % |
| 45 | 4,88% | 0,122 | −6,5 / −9,5 điểm % |
| 50 | 1,87% | 0,069 | −4,5 / −2,0 điểm % |

Ngưỡng `tau` cao nhất của lưới chỉ là `0,10` ở QP≤35. Trong cấu hình có BD-rate tốt nhất, V10 chọn identity cho 180/200 nguồn ở QP30 và 192/200 ở QP35. Guard không giữ đủ lựa chọn tiết kiệm bit để đạt −10% trên CAL. Điều này giải thích **kết quả CAL của chính lưới V10**; nó không chứng minh nguyên nhân kiến trúc của `mc3_18` hoặc khả năng chuyển giao.

Không mở DEV, không điều chỉnh lưới theo kết quả này, và không dùng holdout đã xem để cứu policy. Nếu có thiết kế tiếp theo, phải preregister một nghiên cứu phát triển mới và đánh giá đúng phạm vi dữ liệu của nó.
