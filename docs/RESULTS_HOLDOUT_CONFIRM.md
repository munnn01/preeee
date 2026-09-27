# Xác nhận V2-C trên holdout 1.000 video nguồn

**Kết luận theo tiêu chí đặt trước: KHÔNG ĐẠT.** Policy V2-C đã khóa được đánh giá một lần trên 1.000 source ID mới, cùng tập và thứ tự cho H.264, H.265 và ba analyzer. Đây là phép **confirmatory trên source ID chưa dùng** trong cùng họ Kinetics-400. [Preregistration](PREREGISTRATION.md) và [kiểm toán split](HOLDOUT_SPLIT.md) đã được commit trước lượt chấm. Hai tài liệu khóa đó là ảnh chụp trạng thái *trước* đánh giá, nên câu “chưa chạy” trong chúng mô tả thời điểm khóa. Kết quả thực tế và trạng thái cuối nằm ở tài liệu này.

## Policy V2-C so với `identity128`

BD-rate âm nghĩa là dùng ít bit hơn tại cùng Top-1 theo đường rate–quality. BD-accuracy dương nghĩa là Top-1 cao hơn tại cùng rate. Khoảng tin cậy percentile 95% lấy từ **2.000 bootstrap ghép cặp theo source video**; cả 2.000 draw đều hợp lệ trong mọi ô dưới đây. Mỗi hàng H.264 truy về [h264_result.json](../results/holdout_confirm/h264_result.json); mỗi hàng H.265 truy về [h265_result.json](../results/holdout_confirm/h265_result.json).

| Codec | Analyzer | BD-rate Top-1 (CI 95%) | BD-accuracy, điểm % (CI 95%) |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | −19,70% [−22,17%; −17,06%] | +5,98 [5,13; 6,87] |
| H.264 | `r3d_18` | −12,52% [−14,46%; −10,45%] | +3,55 [2,92; 4,23] |
| H.264 | `mc3_18` | −2,29% [−5,23%; +0,69%] | +0,52 [−0,33; 1,35] |
| H.265 | `r2plus1d_18` | −13,53% [−15,27%; −11,52%] | +6,21 [5,20; 7,17] |
| H.265 | `r3d_18` | −9,08% [−10,47%; −7,67%] | +3,80 [3,10; 4,57] |
| H.265 | `mc3_18` | −1,99% [−4,35%; +0,21%] | +0,75 [−0,17; 1,71] |

**Gate chính giữ nguyên:** ít nhất một codec phải có **cả** `r2plus1d_18` và `r3d_18` với point estimate BD-rate Top-1 **< −15%** và BD-accuracy > 0 so với `identity128`. H.264 trượt vì `r3d_18` là −12,52%; H.265 trượt vì cả hai BD-rate là −13,53% và −9,08%. BD-accuracy dương không cứu được gate. Guard phụ minimum same-QP Top-1 gap của V2-C trên hai analyzer chính là +0,40/+0,20 điểm % ở H.264 và +1,40/+0,40 ở H.265, nên không phải nguyên nhân trượt gate. Không thay ngưỡng theo CI hoặc theo `mc3_18`.

`mc3_18` không tham gia tạo policy. Point estimate tiết kiệm bit nhỏ ở cả codec và **hai CI BD-rate đều chứa 0**; dữ liệu này chưa xác nhận lợi ích chuyển sang analyzer thứ ba. Trên [TEST cũ đã xem](../results/paper_mc3_v2_confirmed/README.md), `mc3_18` có kết quả riêng; không gộp TEST cũ với holdout này.

## Đối chứng giảm độ phân giải đã chốt trước

`area96` và `area112` được áp dụng cố định cho mọi video/QP; chúng đã được nêu trong preregistration. Bảng đầu cho thấy BD-rate của từng baseline so với `identity128`. Bảng sau là **so sánh trực tiếp ghép cặp** của V2-C với từng baseline, dựng lại đường cong từ toàn bộ 1.000 video; đây không phải hiệu của hai BD-rate ở bảng khác. Các số và CI nằm trong khóa `comparisons` của [JSON H.264](../results/holdout_confirm/h264_result.json) và [JSON H.265](../results/holdout_confirm/h265_result.json).

| Codec | Analyzer | `area96` vs identity (CI 95%) | `area112` vs identity (CI 95%) |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | +8,54% [3,90%; 13,21%] | −4,14% [−7,83%; −0,72%] |
| H.264 | `r3d_18` | +12,35% [7,43%; 17,49%] | −2,46% [−6,63%; +1,73%] |
| H.265 | `r2plus1d_18` | +7,32% [4,78%; 9,87%] | −1,19% [−3,71%; +1,43%] |
| H.265 | `r3d_18` | +7,21% [4,03%; 10,28%] | −2,10% [−4,87%; +0,50%] |

| Codec | Analyzer | V2-C vs `area96` (CI 95%) | V2-C vs `area112` (CI 95%) |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | −24,68% [−27,77%; −21,13%] | −14,96% [−17,88%; −11,55%] |
| H.264 | `r3d_18` | −20,14% [−23,48%; −16,47%] | −9,82% [−13,03%; −6,30%] |
| H.265 | `r2plus1d_18` | −16,44% [−18,66%; −13,96%] | −11,71% [−13,80%; −9,56%] |
| H.265 | `r3d_18` | −12,07% [−14,23%; −9,58%] | −6,16% [−8,30%; −3,73%] |

Theo tiêu chí novelty đã chốt, V2-C tốt hơn **cả hai** biến thể downscale cố định trên **cả hai** analyzer chính ở mỗi codec; tám CI so sánh trực tiếp đều nằm dưới 0. Kết luận này chỉ áp dụng cho holdout source-disjoint *trong Kinetics-400*, và **không** thay kết luận gate chính là **KHÔNG ĐẠT**. [Ablation 200 video trên DEV](../results/paper_downscale_dev/README.md) là kết quả khác, không được tính vào bảng holdout.

## Provenance và giới hạn

- ID-only lock commit `c12f422ed85f8a4a61319fe169724c115f663f74`; preregistration/index commit `4730d07df1e9593b56f475ccc395315358f9a49c`, đều có trước lượt chấm. Mã trên Kaggle checkout đúng commit `4730d07…`; mã phân tích gộp tại commit `27f3cc6c52fa6685b3da6a887fa0458fb810b4b4`. Không fit hoặc chọn lại policy từ holdout.
- Fingerprint 1.000 source ID `ea86e9ba66b2fe3143a891619ae34ae036c7f065ea083f4b076b53263e9c668d`; SHA-256 [index](../configs/holdout_source_audit/index.json) `f0f7bd7d56b3b5345886e5be6027c1b1958a9b74efd79ec464eaec096302ec57`. Unit bootstrap là **source video**, giữ mọi QP, arm, codec và analyzer ghép cặp; seed `20260924`, 2.000 resample. Đường cong được gộp từ hai shard 500 record **trước** khi tính BD-rate, không lấy trung bình BD-rate shard.
- SHA-256 [H.264 JSON](../results/holdout_confirm/h264_result.json): `ab2183c1e3851abf0a704624fdfaf1de26d8b5199227b6559d747738b9c36f47`; [H.265 JSON](../results/holdout_confirm/h265_result.json): `7b7125f3623ac0a38fc177dc6ff995cb340eb467d02dfe0feb5c6931bdb78f80`. [SHA256SUMS](../results/holdout_confirm/SHA256SUMS.txt), [run_provenance.json](../results/holdout_confirm/run_provenance.json), [archive_manifest.json](../results/holdout_confirm/archive_manifest.json), bốn notebook riêng tư và tám cặp manifest/record thô trong `results/holdout_confirm/raw/` cho phép truy vết và tái tính.
- Kiểm toán tách nguồn dựa trên source ID cho giao bằng 0 với các inventory V1/V2 có thể truy hồi. Đây **không phải external-domain holdout**; một cảnh bị đổi ID/re-encode có thể không được phát hiện. [Chi phí runtime](RUNTIME_COST.md) của toàn bộ selector cao: overhead trung vị ghép cặp 7,351× H.264 và 7,066× H.265 trên 20 clip DEV. OD/COCO vẫn là pilot 100 ảnh riêng và không hỗ trợ kết luận AR.

Nghiên cứu này vì vậy là **xác nhận âm tính có tái lập và đối chứng**: policy vượt downscale cố định trên nguồn đã khóa, nhưng không đạt ngưỡng tiết kiệm bit đồng thời trên hai analyzer chính; chuyển sang `mc3_18` cũng chưa được xác nhận rõ ràng.
