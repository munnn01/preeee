# Preregistration V3 — policy DEV mới, holdout mới

**Trạng thái: khóa kế hoạch trước khi viết mã V3 hoặc tính kết quả V3 trên DEV.** Đây là nghiên cứu tiếp theo sau [xác nhận âm tính V2-C](RESULTS_HOLDOUT_CONFIRM.md), không phải sửa protocol hay diễn giải lại holdout V2. Kết quả tổng hợp V2 đã được xem khi lập kế hoạch này. Vì vậy **1.000 source ID V2, TEST V1/V2 và analyzer `mc3_18` không được dùng để fit, chọn, hiệu chỉnh hoặc quyết định tiếp tục V3**. Mọi kết luận xác nhận V3 cần một holdout mới, khóa trước khi xem nhãn/kết quả của nó.

## Câu hỏi, đơn vị và gate

V3 hỏi liệu một selector dùng **ngưỡng rủi ro riêng cho từng analyzer và hai nhóm QP** có cải thiện trade-off rate–Top-1 so với V2-C trên DEV, rồi có vượt được gate gốc trên nguồn video mới hay không. Đơn vị độc lập là **source video**; năm QP, sáu candidate, hai codec và các analyzer là phép đo lặp ghép cặp của cùng nguồn. Không xem từng QP/candidate như video độc lập.

**Gate xác nhận giữ nguyên V2:** trên ít nhất một codec, cả `r2plus1d_18` và `r3d_18` phải có point estimate BD-rate Top-1 **< −15%** và BD-accuracy > 0 so với `identity128`. Báo guard minimum same-QP Top-1 gap ≥ −1 điểm phần trăm cho cả hai analyzer. `mc3_18` là phân tích chuyển giao riêng, không thay gate. CI 95% không thay quyết định point estimate. Nếu chưa có holdout mới hợp lệ hoặc chưa chạy xong, kết luận holdout V3 là **CHƯA ĐO**.

## Tập phát triển và ranh giới leakage

Chỉ dùng cache pilot V2 đã đo trước đây trong `D:/STUDY/LAB/proxy_v3/_paper_v2_audit/pilot_{h264,h265}/outputs/dual_codec_search_v2/{codec}/`: 400 source fit, 200 source calibration, 200 source DEV, cùng ID giữa hai codec. Fingerprint manifest của fit là `4c12443af5c0ef44dc5143217ab00b146e0d9090607c49393487d5decd4e4bb1`, calibration `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`, DEV `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`. Kiểm toán source ID cho ba giao bằng 0; mỗi phần cũng có giao bằng 0 với 1.000 source ID holdout V2. Ba phần này đều thuộc **tập phát triển**. Các hash manifest, index và record đầu vào phải được ghi trong artifact V3 trước khi công bố số.

Giữ nguyên risk model logistic đã fit trên 400 source của pilot V2 cho mỗi codec; không refit từ DEV hoặc bất kỳ holdout nào. Chỉ dùng 200 source calibration để chọn ngưỡng V3. Sau khi chọn, đánh giá 200 source DEV **một lần** để báo kết quả thăm dò và quyết định có đáng chạy một holdout mới hay không. Không chỉnh V3 theo DEV sau lần đánh giá đó. V2-C là comparator đã khóa. Không đọc record TEST cũ hay holdout V2 trong script fit/chọn V3; script phải từ chối đường dẫn vào các tập này.

## Policy và phép chọn trên calibration

Giữ nguyên sáu candidate pixel trước codec, năm QP `30,35,40,45,50`, H.264/H.265 `medium`, 16 frame 128×128, các đặc trưng analyzer và risk model V2. Selector V3 không nhận nhãn hay `correct`/`cross_correct`: dùng `observations()` để loại outcome trước khi lựa chọn. Giữ guard primary V2-C cho `r2plus1d_18` (`kl=0.1`, `feature=0.05`, `confidence=0.6`). Với mỗi candidate tiết kiệm bit, yêu cầu risk dự báo của **từng** analyzer không quá ngưỡng riêng; dùng cặp ngưỡng “low” cho QP ≤35 và “high” cho QP ≥40. Trong tập feasible chọn candidate có bpp nhỏ nhất, tie-break theo thứ tự candidate gốc; `identity128` luôn feasible.

Grid cố định gồm `low_r2`, `low_r3` trong `{0.05, 0.10, 0.20}` và `high_r2`, `high_r3` trong `{0.10, 0.20, 0.30}`: đúng **81** policy, gồm V2-C (`0.10,0.10,0.20,0.20`). Đánh giá toàn bộ 81 trên cùng 200 source calibration. Policy khả thi khi trên **cả hai** analyzer: BD-rate và BD-accuracy xác định, BD-rate <0, BD-accuracy >0 và minimum same-QP gap ≥ −1 điểm phần trăm. Trong số khả thi, chọn policy có `max(BD-rate_r2, BD-rate_r3)` nhỏ nhất; tie-break bằng tổng hai BD-rate rồi thứ tự tuple ngưỡng tăng dần. Đây là tối ưu worst analyzer đặt trước, không chọn theo TEST/holdout hoặc `mc3_18`.

Áp dụng phép chọn **riêng theo codec**. Chỉ gọi policy được chọn là **V3 candidate** nếu worst BD-rate trên calibration tốt hơn V2-C ít nhất **1,00 điểm phần trăm** và BD-rate của từng analyzer không kém V2-C quá **0,50 điểm phần trăm**. Codec không đạt điều kiện này dùng nguyên V2-C làm fallback, không gọi fallback là policy mới. Nếu cả hai codec đều fallback, báo toàn bộ grid và dừng trước holdout mới. Không đổi margin sau khi xem grid.

Trên 200 source DEV, báo V3 candidate (hoặc fallback) và V2-C so với identity, đồng thời so sánh trực tiếp V3 với V2-C: năm điểm curve, BD-rate, BD-accuracy, minimum same-QP gap, choice counts và CI percentile 95% từ **2.000** bootstrap theo source video, seed `20260928`. Không dùng DEV để đổi ngưỡng. Chỉ mở lượt xác nhận đắt tiền nếu trên DEV **một codec có V3 candidate mới** với BD-rate tốt hơn V2-C ở **cả hai** analyzer, BD-accuracy >0 và guard đạt. Đây là **go/no-go chi phí**, không phải tiêu chí xác nhận hay thay thế gate < −15%. Nếu không qua go/no-go, công bố kết quả DEV là exploratory và dừng; không xem holdout mới.

## Holdout V3 độc lập và lượt xác nhận

Nguồn ứng viên là các source ID official Kinetics-400 validation CVDF đã kiểm toán. Trừ **toàn bộ** source ID lịch sử V1/V2, ba phần fit/calibration/DEV nêu trên và 1.000 ID holdout V2. Xếp ID còn lại theo `SHA256("v3-source-holdout-20260927\0" + source_id)`, chỉ dùng ID. Chọn **1.000 ID đầu tiên có video đọc được**, một clip/source; preflight chỉ kiểm tra byte và giải mã, không đọc nhãn hoặc kết quả. Chốt danh sách ID, SHA-256 video và fingerprint bằng commit **trước** khi tạo index nhãn. Không thay clip theo lớp, bitrate, hình ảnh hoặc Top-1. Nếu không có 1.000 nguồn hợp lệ hoặc không chứng minh được disjoint, holdout V3 = **CHƯA ĐO**. Đây tiếp tục là tách source trong cùng Kinetics, **không** phải external-domain holdout.

Chỉ sau khi V3 candidate đã freeze và vượt go/no-go DEV, commit protocol/index/frozen policy rồi chạy **một lần** trên 1.000 source V3: hai codec, hai analyzer chính, `mc3_18` chỉ để chuyển giao, V2-C đối chứng, `identity128`, `area96`, `area112`. Dùng mọi stream đã được frozen policy chọn; không cho `mc3_18` tham gia selection. Gộp hai shard 500 thành toàn bộ curve trước khi tính BD-rate. Bootstrap 2.000 resample theo source video với seed `20260928`, giữ các arm/analyzer/QP/codec ghép cặp. Báo kết quả bất lợi, số draw hợp lệ, SHA-256 config/index/record/kết quả, commit code và fingerprint. Không dùng holdout V2 để quyết định hay sửa V3; holdout V2 chỉ xuất hiện trong báo cáo như nghiên cứu tiền nhiệm.

## Diễn giải

Nếu V3 trượt gate trên holdout mới, ghi **KHÔNG ĐẠT** và giữ đây là một negative study thứ hai. Nếu V3 qua gate, giới hạn kết luận vào source-disjoint Kinetics và đúng ba analyzer đã đo; không suy ra chuyển miền, OD hay chi phí triển khai tốt nếu chưa đo. Một policy khác được thử sau khi thấy holdout V3 phải dùng preregistration và holdout **khác nữa**.
