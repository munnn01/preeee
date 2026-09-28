# Kết quả xác nhận V4 trên 1.000 source video mới

Policy V4, mô hình, nguồn video, index, gate và phép phân tích đã khóa trước lượt chấm theo [preregistration V4](PREREGISTRATION_V4.md), [kiểm toán split](HOLDOUT_SPLIT_V4.md) và [amendment kỹ thuật](V4_HOLDOUT_TECHNICAL_AMENDMENT.md). Đây là holdout **source-disjoint trong Kinetics-400**, không phải dataset ngoài miền. H.264 và H.265 dùng cùng 1.000 nguồn, chia hai shard 500; đường cong được gộp từ record nguồn trước khi tính BD-rate. Mỗi CI percentile 95% dùng 2.000 resample ghép cặp theo **source video**, seed `20260928`. Số H.264 dưới đây truy về [JSON H.264](../results/paper_holdout_v4/h264_result.json), số H.265 về [JSON H.265](../results/paper_holdout_v4/h265_result.json). Giá trị BD-accuracy có đơn vị điểm phần trăm.

## Gate chính đã đăng ký

| Codec | Analyzer | V4 so với identity: BD-rate Top-1, CI 95% | BD-accuracy, CI 95% | Worst same-QP Top-1 gap |
|---|---|---:|---:|---:|
| H.264 | `r2plus1d_18` | **−22,11%** [−24,16%; −19,93%] | +6,56 [5,63; 7,53] | −0,10 |
| H.264 | `r3d_18` | **−23,63%** [−25,84%; −21,22%] | +6,69 [5,78; 7,64] | −0,20 |
| H.265 | `r2plus1d_18` | −14,16% [−15,61%; −12,58%] | +6,71 [5,76; 7,71] | +0,20 |
| H.265 | `r3d_18` | −12,11% [−13,64%; −10,39%] | +4,66 [3,81; 5,48] | +0,40 |

**Gate đặt trước ĐẠT qua H.264:** ở ít nhất một codec, *cả hai* analyzer chính có point estimate BD-rate Top-1 **< −15%** và BD-accuracy > 0 so với `identity128`. H.264 còn đạt guard same-QP ≥ −1 điểm phần trăm. H.265 **không đạt gate riêng codec** vì cả hai BD-rate đều > −15%. Gate xét point estimate như đã khóa; CI được báo để biểu thị bất định, không dùng để đổi quy tắc.

## Analyzer thứ ba độc lập

| Codec | `mc3_18`: BD-rate Top-1, CI 95% | BD-accuracy, CI 95% | Worst same-QP Top-1 gap |
|---|---:|---:|---:|
| H.264 | +1,92% [−2,31%; +5,81%] | −0,96 [−2,02; +0,17] | −8,30 |
| H.265 | −0,50% [−3,10%; +2,19%] | +0,32 [−0,81; +1,45] | −7,50 |

`mc3_18` không tham gia fit, calibration hay lựa chọn policy V4. Hai CI BD-rate đều chứa 0; **chưa có bằng chứng về lợi ích chuyển giao**. Top-1 của V4 thấp hơn identity ở **cả năm QP của cả hai codec**; riêng H.264 các gap lần lượt là −5,0, −8,3, −5,4, −6,9 và −4,0 điểm phần trăm tại QP 30–50. Điều này quan trọng dù tích phân BD-accuracy H.265 dương nhẹ. `mc3_18` không nằm trong gate chính đã đăng ký, nên kết quả yếu của nó không được giấu trong kết luận “ĐẠT”.

## Đối chứng V2-C trên cùng nguồn mới

| Codec | Analyzer | V2-C so với identity: BD-rate, CI 95% | V4 so với V2-C trực tiếp: BD-rate, CI 95% |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | −20,68% [−23,17%; −18,03%] | −2,43% [−4,84%; +0,30%] |
| H.264 | `r3d_18` | −12,17% [−14,15%; −10,02%] | −13,08% [−15,11%; −11,21%] |
| H.265 | `r2plus1d_18` | −13,88% [−15,63%; −12,01%] | −1,02% [−2,44%; +0,36%] |
| H.265 | `r3d_18` | −7,95% [−9,27%; −6,43%] | −4,37% [−5,68%; −3,02%] |

So sánh trực tiếp dựng lại curve ghép cặp, **không trừ hai BD-rate** từ các cột khác. Cải thiện V4 so với V2-C trên `r3d_18` rõ ở cả codec. Khoảng tin cậy của cải thiện trên `r2plus1d_18` cắt 0; không khẳng định hơn V2-C ở analyzer đó. V2-C ở đây được chấm trên **holdout V4**, khác với [holdout V2 đã công bố](RESULTS_HOLDOUT_CONFIRM.md) và [TEST V1/V2 cũ](../results/dual_codec_search_v2_confirm_1000/README.md). Không gộp các quần thể đó thành một kết quả.

## Diễn giải và giới hạn

V4 chọn `area96` ở 3.241/5.000 cặp source–QP H.264 (64,82%) và 2.734/5.000 H.265 (54,68%); đây là thống kê hậu nghiệm từ khóa `choices` trong hai JSON. Nó xuất hiện cùng suy giảm Top-1 `mc3_18`, **chưa chứng minh nhân quả**: trong giao thức này `mc3_18` chỉ chấm identity và stream V4 đã chọn, không chấm toàn bộ candidate. Không được dùng holdout vừa xem để chọn ngưỡng hoặc policy khác rồi gọi cùng holdout là xác nhận độc lập.

Ở lượt Kaggle đầu, ít nhất shard H.265 số 1 dừng tại bước kiểm tra hash CRLF/LF của V2 comparator **trước khi tạo record chấm**; [amendment](V4_HOLDOUT_TECHNICAL_AMENDMENT.md) ghi nguyên nhân và sửa đúng kiểm tra byte, không sửa policy hay gate. Mọi artifact từ lượt đầu được loại khỏi phân tích xác nhận, kể cả nếu shard khác đã tạo được record. Bốn shard hoàn tất sau sửa được lưu cùng manifest/record thô và hash trong [gói kết quả](../results/paper_holdout_v4/README.md). Hai lượt chạy lại lệnh merge từ record thô tạo JSON **trùng SHA-256 từng byte** với kết quả lưu. SHA-256 H.264: `9991b7cc027e4d551317e37ecf8c4d70f92cb9ee9a00e98f0d10927502fce2f4`; H.265: `4ad877538d08494de0eeec1954c5467f816e144a49d0559371b14a9b3c4a8814`. `analysis_code_commit` và `preregistration_commit` trong JSON đều là `9b6805bf994bfc9e237049abf2adccec4f3f59cf`; khóa ID có từ commit `969d2f2d71575e61e95ea2849f533d4a56e522fa`, index được commit tại `78c1124d092d70ba11f3ed664194e4f747f5e3a8`. Fingerprint source `b72321eecafe6f81368ae22e5352f04305094634aaca2a378bac12b7cc60822b`; SHA-256 index `995969ffdc943976400c67337ca3d27c95370f22040f64e2fa43169e08efe8e2`.

Chi phí runtime toàn bộ selector V4: **CHƯA ĐO**. Số overhead trong [RUNTIME_COST.md](RUNTIME_COST.md) chỉ đo V2-C, không chuyển sang V4. OD/COCO vẫn là pilot exploratory riêng và không phải bằng chứng cho kết luận AR. Cần nguồn ngoài Kinetics hoặc một holdout source-disjoint mới cùng analyzer chưa tham gia phát triển nếu muốn xác nhận một policy tiếp theo.
