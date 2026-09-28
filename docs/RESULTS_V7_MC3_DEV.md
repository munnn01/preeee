# V7 H.265 trên `mc3_18`: chẩn đoán 200 nguồn DEV đã dùng

**Kết quả quan sát: V7 không cải thiện `mc3_18` so với V6 trên DEV.** BD-rate Top-1 trực tiếp V7 so với V6 là **+1,70%**, CI 95% [−0,77%; +4,33%]. Dấu dương là tốn bitrate hơn ở cùng Top-1 theo đường cong; CI chứa 0 nên cũng không đủ bằng chứng về một mức suy giảm chắc chắn. V7 so với identity là −0,46% [−4,19%; +2,91%], gần 0 và không có bằng chứng giảm bitrate trên analyzer này. Không dùng `mc3_18` để fit, chọn hay hiệu chỉnh V7 sau lượt đo.

| So sánh H.265, 200 nguồn | BD-rate Top-1 | CI 95% | BD-accuracy, điểm % | CI 95% BD-accuracy | Worst same-QP Top-1 gap, điểm % |
|---|---:|---:|---:|---:|---:|
| V6 vs identity | −2,02% | [−6,00%; +1,45%] | +1,03 | [−1,28; +3,47] | −6,00 |
| V7 vs identity | −0,46% | [−4,19%; +2,91%] | +0,05 | [−2,23; +2,42] | −7,50 |
| **V7 vs V6 trực tiếp** | **+1,70%** | **[−0,77%; +4,33%]** | **−1,03** | [−2,68; +0,50] | −1,50 |

Đường cong Top-1 nguồn gộp cho thấy V7 có bpp thấp hơn V6 ở QP 30–40, nhưng cao hơn ở QP 45–50; Top-1 thấp hơn V6 từ 1,0 đến 1,5 điểm % ở cả năm QP. Mẫu này giải thích point BD-rate dương, không phải phân tích chọn policy.

| QP | Identity: bpp / Top-1 | V6: bpp / Top-1 | V7: bpp / Top-1 |
|---:|---:|---:|---:|
| 30 | 0,303434 / 72,5% | 0,234072 / 66,5% | 0,228248 / 65,5% |
| 35 | 0,197047 / 63,0% | 0,164975 / 57,0% | 0,162641 / 55,5% |
| 40 | 0,139011 / 50,0% | 0,126871 / 46,0% | 0,126534 / 45,0% |
| 45 | 0,106964 / 27,5% | 0,103283 / 28,5% | 0,103867 / 27,5% |
| 50 | 0,091065 / 9,5% | 0,090345 / 11,0% | 0,090843 / 10,0% |

Phép đo theo [giao thức khóa trước](PREREGISTRATION_V7_MC3_DEV.md), commit `53a1ad44c9c659829d97046e117e9d50928dada1`. Lựa chọn 200×5 stream được [commit trước suy luận](../configs/v7_mc3_dev_selection.json), SHA-256 `74404de548e85587fad3c0108697780c6ef94108b160cfd17d2926c5163eacec`, tại commit `4b948bbf3414bd0cc42c908ca2d795a1a2919c6e`. Cùng commit này chứa worker và merge. Bốn notebook private chạy 50 nguồn rời nhau: [shard 0](https://www.kaggle.com/code/shungg05/v7-mc3-dev-s0-4b948bb), [shard 1](https://www.kaggle.com/code/dieulinhh/v7-mc3-dev-s1-4b948bb), [shard 2](https://www.kaggle.com/code/huolgggnuyen/v7-mc3-dev-s2-4b948bb), [shard 3](https://www.kaggle.com/code/baooo25r/v7-mc3-dev-s3-4b948bb). Cả bốn hoàn tất với Torch `2.10.0+cu128`, TorchVision `0.25.0+cu128`, FFmpeg `4.4.2-0ubuntu0.22.04.1` và CUDA.

Mỗi source video khớp SHA-256 đã ghi từ phép trích proxy V7; mọi bitrate tái mã hóa khớp cache V2 theo dung sai đã khóa `1e-9`. Merge kiểm tra đúng 200 ID duy nhất, fingerprint `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`, đường cong toàn bộ nguồn trước BD-rate, và 2.000 bootstrap percentile **theo source video**, seed `20261004`, ghép cả ba arm và năm QP. Cả ba so sánh có 2.000/2.000 resample hợp lệ. Hai lần merge với thứ tự shard khác nhau tạo cùng SHA-256 kết quả `03210936fc1d9eb88324f3b3066756a811ae43c914d2f75c8181d9c9aec8e25d`. [JSON gộp](../results/v7_mc3_dev/mc3_h265_dev_result.json), [raw record, archive và log](../results/v7_mc3_dev/README.md) lưu provenance và mọi số trong bảng.

Kết quả trên hai analyzer chính của V7 vẫn là **−16,21%** (`r2plus1d_18`) và **−11,21%** (`r3d_18`) so với identity, với CI và điều kiện trong [báo cáo DEV gốc](RESULTS_V7_DEV.md) và [JSON DEV](../results/v7_dev_transfer/h265_result.json). Chúng qua mục tiêu kỹ thuật point <−10% nhưng gate nghiên cứu gốc <−15% trên cả hai analyzer vẫn **KHÔNG ĐẠT**. Lượt `mc3_18` này dùng chính 200 nguồn DEV pilot đã được dùng phát triển, và kết quả `mc3_18` lịch sử từng được xem ở V2/V4/V6. Vì vậy đây không phải xác nhận trên nguồn độc lập hoặc kiến trúc chưa từng quan sát. **V7 holdout mới: CHƯA ĐO.** Không đổi policy sau kết quả này và không dùng holdout V6 để xác nhận V7.
