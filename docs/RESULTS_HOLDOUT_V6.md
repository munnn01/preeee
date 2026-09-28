# Kết quả xác nhận V6 H.265 trên 1.000 video nguồn mới

Policy V6 H.265, V2-C comparator, danh sách ID, hash byte video, index nhãn, gate và phép phân tích được khóa theo [preregistration](PREREGISTRATION_V6_HOLDOUT.md) và [kiểm toán nguồn](HOLDOUT_SPLIT_V6.md) trước khi chạy analyzer. Giao thức đầu tiên được commit tại `385674ddf93d477d78f0b6b1b4abdff667eee7e5`; ID và hash video tại `dd3f5a14708ca37a9db537d17ca23638a4dfc855`, trước khi đọc nhãn; index và mã phân tích tại `de9d37866216649e978b263a3af1ad4ab9e5d6e7`, trước khi chấm. Đây là tập **source-ID-disjoint trong Kinetics-400**, không phải dữ liệu ngoài miền. Đánh giá V6 chỉ đăng ký **H.265**; H.264 V6 **CHƯA ĐO**.

Hai shard, mỗi shard 500 source, được gộp thành curve 1.000 source trước khi tính BD-rate. Mỗi CI percentile 95% dùng 2.000 resample ghép cặp theo **source video**, giữ đủ QP/arm/analyzer trong mỗi lần rút, seed `20261001`; mọi CI bên dưới có 2.000/2.000 draw hợp lệ. Tất cả số ở đây lấy từ [h265_result.json](../results/paper_holdout_v6/h265_result.json), SHA-256 `69d387c2c8fd7c6286228eda3bde211f32e9ca58ae82104dec41c7cb2654fdad`. [Gói record thô và provenance](../results/paper_holdout_v6/README.md) cho phép kiểm toán lại phép gộp; hai lần chạy merge từ cùng record tạo JSON trùng SHA-256 từng byte.

## Gate chính đã đăng ký

| Analyzer | V6 so với identity: BD-rate Top-1, CI 95% | BD-accuracy (điểm %), CI 95% | Worst same-QP Top-1 gap (điểm %) |
|---|---:|---:|---:|
| `r2plus1d_18` | **−13,62%** [−15,41%; −11,69%] | +6,47 [5,51; 7,42] | +0,90 |
| `r3d_18` | **−11,11%** [−12,71%; −9,19%] | +5,19 [4,23; 6,07] | +0,40 |

**H.265 V6 KHÔNG ĐẠT gate đặt trước.** Gate yêu cầu cả hai analyzer chính có *point estimate* BD-rate Top-1 **< −15%** và BD-accuracy > 0 so với identity ở cùng codec. BD-accuracy dương và same-QP gap không âm, nhưng cả hai BD-rate đều chưa vượt ngưỡng. Không dùng phần dưới của CI hay kết quả V4 H.264 để đổi quyết định. Vì H.264 V6 chưa được đo, **không có bằng chứng V6 đạt gate ở bất kỳ codec nào đã chấm**; không tuyên bố gate tổng thể đạt.

## So sánh trực tiếp với V2-C trên cùng 1.000 nguồn

| Analyzer | V2-C so với identity: BD-rate, CI 95% | V6 so với V2-C trực tiếp: BD-rate, CI 95% | BD-accuracy V6 so với V2-C (điểm %) |
|---|---:|---:|---:|
| `r2plus1d_18` | −12,89% [−14,61%; −11,11%] | −0,85% [−1,73%; −0,01%] | +0,36 |
| `r3d_18` | −8,94% [−10,30%; −7,38%] | −2,36% [−3,50%; −1,07%] | +1,31 |
| `mc3_18` | −1,75% [−3,77%; +0,42%] | **+1,53% [−0,49%; +3,32%]** | −0,86 |

So sánh trực tiếp dùng curve ghép cặp, không lấy hiệu hai BD-rate so với identity. V6 có cải thiện BD-rate nhỏ trên hai analyzer dùng trong phát triển, với CI trực tiếp đều dưới 0. Nhưng chiều điểm của `mc3_18` là **xấu hơn V2-C**, CI chứa 0; không chứng minh cải thiện `mc3_18`, cũng chưa xác lập chắc chắn mức suy giảm BD-rate. `mc3_18` không tham gia fit/chọn V6, nhưng kết quả của kiến trúc này ở nghiên cứu trước đã được xem: đây là kiểm tra chuyển giao sang **source mới**, không phải kiến trúc chưa từng quan sát trong toàn bộ quá trình nghiên cứu.

Riêng V6 so với identity trên `mc3_18`: BD-rate **−0,25%** [−2,53%; +1,99%], BD-accuracy −0,01 điểm %, worst same-QP Top-1 gap **−4,20 điểm %**. Top-1 identity → V6 lần lượt là 51,1% → 48,4% (QP30), 47,7% → 44,3% (QP35), 38,9% → 34,7% (QP40), 24,0% → 22,7% (QP45), 8,7% → 9,3% (QP50). Các mức giảm ở QP35/40 quan trọng dù BD-rate tích phân gần 0. Không suy diễn một cơ chế nhân quả từ thống kê lựa chọn stream của holdout.

## Đối chứng downscale thuần

Hai đối chứng cố định được đăng ký trước: `area96` có BD-rate so với identity **+5,26%** [2,68%; 7,79%] trên `r2plus1d_18`, **+8,18%** [5,23%; 11,20%] trên `r3d_18`; `area112` lần lượt **+0,85%** [−1,67%; 3,26%] và **−1,93%** [−4,40%; +0,46%]. So sánh V6 với baseline tương ứng, tính trực tiếp từ curve ghép cặp: so với `area96`, **−15,87%** [−17,93%; −13,70%] và **−14,11%** [−16,31%; −11,67%]; so với `area112`, **−13,81%** [−15,90%; −11,62%] và **−8,51%** [−10,39%; −6,55%] trên hai analyzer theo thứ tự. Điều này hỗ trợ giá trị của chọn stream so với hai kích thước downscale cố định ở **cùng tập và codec**, nhưng không giải quyết thất bại của gate hay `mc3_18`.

## Provenance và giới hạn

Source fingerprint: `269998dbd77c69b5a990f637506d7e1f4f6af4f9e59c38058d000a44535ce918`; index SHA-256: `37d7ff5d0763b00f2e335e84012611345438d0ade3ffb216d6ada46542678ce3`; frozen manifest SHA-256: `bedb316eacf9167a6db2b766c1b00aef5cf5dcaa333ae65e56c2333349e0eadb`. [run_provenance.json](../results/paper_holdout_v6/run_provenance.json) ghi model hash, raw record hash, Kaggle notebook, seed và commit. Hai archive gốc có hash trong [archive_manifest.json](../results/paper_holdout_v6/archive_manifest.json). V6 chọn `area112` ở 2.331/5.000 cặp source–QP, tăng so với 686/5.000 của V2-C; đây chỉ là mô tả hậu nghiệm, **không** dùng để sửa policy trên holdout này.

Kết quả V6 là một phép xác nhận **âm tính theo gate đã khóa**, dù hai analyzer chính cải thiện nhỏ so với V2-C. `mc3_18` vẫn là điểm yếu chuyển giao. Không dùng 1.000 source này để tune hay chọn V7 rồi gọi chúng là holdout độc lập. Tách source ID không loại trừ video đăng lại dưới ID khác. Runtime đầy đủ của selector V6 **CHƯA ĐO**; [runtime V2-C](RUNTIME_COST.md) không thay thế phép đo đó. Pilot OD 100 ảnh COCO không được dùng làm bằng chứng cho kết luận AR.
