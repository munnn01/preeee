# V11 H.265: kết quả và đánh giá trên 200 nguồn DEV đã dùng lại

**V11 KHÔNG ĐẠT gate phát triển (NO-GO).** Hai analyzer chính có point BD-rate <−10%, nhưng `mc3_18` trượt CI upper ≤+1% và worst same-QP gap ≥−1,00 điểm %. Gate nghiên cứu gốc yêu cầu cả hai analyzer chính BD-rate <−15% và BD-accuracy >0 cũng **KHÔNG ĐẠT trên DEV này**. **V11 holdout nguồn mới: CHƯA ĐO.** Theo [preregistration đã khóa](PREREGISTRATION_V11_112_RESIDUAL.md), dừng V11 trước một nghiên cứu xác nhận mới; không thay ngưỡng hoặc chọn lại policy sau scoring.

## 1. Dữ liệu và phép phân tích

Bốn job private đã hoàn tất, mỗi job 50 nguồn, tổng 200 nguồn DEV Kinetics-400 đã dùng trong nghiên cứu trước. H.265/libx265 preset medium, năm QP 30, 35, 40, 45, 50; năm arm identity, area112 cố định, V2-C, V6, V11; ba analyzer đóng băng. [Kiểm toán](../results/v11_spatial_dev/validation.json) xác nhận nguồn/hash, manifest/record/sidecar, lựa chọn đã commit trước suy luận, bpp/coded bytes, pixel decode của stream proxy, label/prediction, cùng trọng số/phiên bản ở cả bốn shard. Có **2.493 trial encode/decode** (618/606/652/617); stream dùng chung được tính một lần, chấm trên cả ba analyzer. Đây là trial đánh giá, chưa phải đo runtime toàn selector.

Gộp record của đủ nguồn rồi dựng đường cong toàn bộ năm QP. Dùng nguyên `src/metrics/bd_rate.py` và `ops.v8_motion_pilot.summarize`; không lấy trung bình BD-rate của shard. CI 95% percentile từ **2.000 bootstrap theo source video**, numpy `default_rng(20261008)`, ghép tất cả QP, arm và analyzer trong cùng draw. Mọi BD-rate và BD-accuracy ở cả bảy so sánh × ba analyzer đều có **2.000/2.000 draw hợp lệ**. [JSON gộp](../results/v11_spatial_dev/h265_result.json) là nguồn cho mọi metric/CI dưới đây.

Tập này là DEV đã dùng lại, không phải holdout độc lập. `mc3_18` không tham gia CAL/fit/chọn V11; các kết quả lịch sử của nó đã ảnh hưởng giả thuyết, nên chỉ gọi là analyzer chuyển giao, không phải kiến trúc chưa từng quan sát. Không chấm lại TEST/holdout và không chạy holdout mới trong lượt này.

## 2. V11 so với identity

| Analyzer | BD-rate Top-1 | CI 95% BD-rate | BD-accuracy, điểm % | CI 95% BD-accuracy | Worst same-QP gap, điểm % |
|---|---:|---:|---:|---:|---:|
| `r2plus1d_18` | −16,10% | [−19,29; −12,80]% | +11,50 | [+9,01; +14,21] | +1,00 |
| `r3d_18` | −10,23% | [−12,62; −7,61]% | +6,04 | [+4,00; +7,95] | +0,00 |
| `mc3_18` | −2,09% | [−6,04; +1,55]% | +1,15 | [−1,33; +3,59] | −6,00 |

| Analyzer | Rate gate | BD-accuracy >0 | Gap ≥−1 pp | ≥1.900 draw hợp lệ | CI mc3 upper ≤+1% |
|---|---|---|---|---|---|
| `r2plus1d_18` | ĐẠT | ĐẠT | ĐẠT | ĐẠT | Không áp dụng |
| `r3d_18` | ĐẠT | ĐẠT | ĐẠT | ĐẠT | Không áp dụng |
| `mc3_18` | ĐẠT | ĐẠT | KHÔNG ĐẠT | ĐẠT | KHÔNG ĐẠT |

Hai analyzer chính qua quy tắc **point estimate**, không có yêu cầu CI toàn bộ dưới −10% trong preregistration. `r3d_18` chỉ đạt −10,23%, CI upper −7,61%, nên margin so với mục tiêu −10% còn nhỏ. `mc3_18` có BD-rate âm nhưng CI chứa 0 và upper +1,55% >+1%; BD-accuracy point dương nhưng CI cũng chứa 0. BD-rate là phép so sánh rate ở cùng quality trên miền chồng lấp của đường cong, vì vậy một giá trị âm vẫn có thể đi cùng mất Top-1 nghiêm trọng ở một QP. Guard same-QP giữ nguyên để phản ánh rủi ro này.

## 3. So với V2-C, V6 và downscaling thuần trên chính DEV này

| Policy so với identity | `r2plus1d_18` | `r3d_18` | `mc3_18` |
|---|---:|---:|---:|
| V2-C | −14,87% | −8,60% | −3,06% |
| V6 | −16,26% | −10,69% | −2,02% |
| V11 | −16,10% | −10,23% | −2,09% |
| area112 cố định | −2,63% | +0,45% | −1,10% |

Không ghép những số này với số CAL hoặc holdout cũ để tính mức cải thiện. Đối chứng bên dưới được tái chấm cùng nguồn, codec, trọng số và bootstrap với V11.

### So trực tiếp V11 với V6

| Analyzer | BD-rate Top-1 | CI 95% BD-rate | BD-accuracy, điểm % | CI 95% BD-accuracy | Worst same-QP gap, điểm % |
|---|---:|---:|---:|---:|---:|
| `r2plus1d_18` | +0,19% | [+0,13; +0,25]% | −0,13 | [−0,18; −0,09] | +0,00 |
| `r3d_18` | +0,36% | [+0,17; +0,66]% | −0,22 | [−0,37; −0,11] | −1,00 |
| `mc3_18` | −0,07% | [−0,93; +0,73]% | +0,11 | [−0,35; +0,69] | −0,50 |

Trên `mc3_18`, point cải thiện trực tiếp chỉ −0,07%, CI [−0,93%; +0,73%] chứa 0: **chưa có bằng chứng cải thiện chuyển giao so với V6**. Hai analyzer chính bị tăng BD-rate nhỏ (+0,19% và +0,36%), với CI trực tiếp đều nằm phía dương trên DEV này. R2 giữ nguyên mọi dự đoán đúng/sai nhưng V11 tốn thêm bit; R3 mất thêm hai dự đoán đúng tại QP 50. Đây là chi phí có đo được, dù nhỏ.

### So trực tiếp V11 với V2-C

| Analyzer | BD-rate Top-1 | CI 95% BD-rate | BD-accuracy, điểm % | CI 95% BD-accuracy | Worst same-QP gap, điểm % |
|---|---:|---:|---:|---:|---:|
| `r2plus1d_18` | −1,56% | [−3,08; −0,04]% | +1,08 | [+0,11; +2,02] | −1,00 |
| `r3d_18` | −1,80% | [−3,42; −0,09]% | +1,24 | [+0,03; +2,43] | −0,50 |
| `mc3_18` | +0,91% | [−2,20; +4,74]% | −0,72 | [−2,68; +0,96] | −3,00 |

V11 giữ lợi ích hai analyzer chính của V6 so với V2-C, nhưng `mc3_18` có point BD-rate trực tiếp +0,91%, CI chứa 0. Nó chưa cải thiện được analyzer chuyển giao so với V2-C.

### So trực tiếp V11 với area112 cố định

| Analyzer | BD-rate Top-1 | CI 95% BD-rate | BD-accuracy, điểm % | CI 95% BD-accuracy | Worst same-QP gap, điểm % |
|---|---:|---:|---:|---:|---:|
| `r2plus1d_18` | −12,61% | [−15,98; −8,86]% | +9,45 | [+6,70; +12,13] | +6,00 |
| `r3d_18` | −10,25% | [−13,13; −6,85]% | +6,28 | [+3,98; +8,49] | +2,00 |
| `mc3_18` | −0,96% | [−4,39; +2,33]% | −0,04 | [−2,03; +2,00] | −2,00 |

Hai analyzer chính có CI BD-rate trực tiếp hoàn toàn âm: selector có giá trị vượt baseline area112 cố định trên DEV này. Với `mc3_18`, CI BD-rate/BD-accuracy đều chứa 0, point BD-accuracy là −0,04 điểm %, và worst gap trực tiếp −2 điểm %; chưa có bằng chứng lợi ích vượt downscaling thuần trên analyzer này. Đây chưa phải bằng chứng tổng quát hóa.

## 4. Nút thắt theo QP của `mc3_18`

Các Top-1, số đổi stream và flip correctness sau freeze đến từ [diagnostics.json](../results/v11_spatial_dev/diagnostics.json); thiếu hụt so với guard là phép tính số học trong [guard_deficits.json](../results/v11_spatial_dev/guard_deficits.json), không phải kết quả của một policy mới.

| QP | Số đổi stream / 200 | Identity Top-1 | V2-C Top-1 | V6 Top-1 | V11 Top-1 | V11 − identity, điểm % | V11 − V6, điểm % | Số dự đoán đúng ròng còn thiếu để gap ≥−1 pp |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 30 | 0 | 72,50% | 65,50% | 66,50% | 66,50% | −6,00 | +0,00 | 10 |
| 35 | 6 | 63,00% | 60,50% | 57,00% | 57,50% | −5,50 | +0,50 | 9 |
| 40 | 9 | 50,00% | 49,50% | 46,00% | 46,50% | −3,50 | +0,50 | 5 |
| 45 | 28 | 27,50% | 27,00% | 28,50% | 28,00% | +0,50 | −0,50 | 0 |
| 50 | 52 | 9,50% | 10,50% | 11,00% | 10,50% | +1,00 | −0,50 | 0 |

V11 không đổi stream ở QP 30, giữ nguyên gap −6,00 pp nơi `mc3_18` mất nhiều nhất. QP 35/40 chỉ lấy lại mỗi QP một dự đoán đúng ròng, còn QP 45/50 mất mỗi QP một. Trong 1.000 cặp nguồn–QP, `mc3_18` có **4 gain / 4 loss / net 0** so với V6; R2 có **0/0**, R3 **0/2**. Cặp ở các QP dùng chung video, không phải 1.000 mẫu độc lập.

Để đạt guard với Top-1 identity quan sát giữ cố định, QP 30 cần thêm **10** dự đoán đúng ròng trong 200 nguồn; QP 35 cần **9**, QP 40 cần **5**. Các số này chỉ lượng hóa khoảng cách tới gate, không chứng minh rằng một selector khác sẽ lấy lại được chúng và không cộng chúng thành số video độc lập.

[Proxy DEV đã kiểm toán](../results/v11_spatial_dev_proxy/diagnostics.json) giảm D112 trung bình 1,54%, nhưng **80/95** lần đổi stream ở QP 45–50; mean bpp cùng QP tăng +0,12%. Proxy cải thiện về sai khác gradient/Laplacian đã đo, chưa dự báo được lợi ích ngữ nghĩa cho `mc3_18`. Kết quả này không xác định quan hệ nhân quả giữa kiến trúc MC3 và downscaling; nó chỉ bác bỏ việc dùng mức giảm D112 hiện tại làm bằng chứng rằng chuyển giao đã được sửa.

## 5. Tính khả thi và hướng tiếp theo

- **Giữ hai analyzer chính dưới −10%:** có point estimate đạt trên DEV, nhưng R3 có ít margin; chưa chứng minh chắc chắn trên nguồn mới.
- **Cải thiện `mc3_18` ổn định:** chưa đạt. Sửa proxy trên lưới 112 và chuyển V6→V2 có điều kiện chủ yếu can thiệp QP cao; mất mát cần giải quyết vẫn ở QP 30–40. Tiếp tục dùng V11 đã freeze không đáp ứng toàn bộ mục tiêu đo được.
- **Nghiên cứu kế tiếp cần tập trung vào selector bảo vệ QP thấp:** trên FIT/CAL, kiểm chứng giả thuyết cho phép chọn identity trực tiếp ở QP 30–40 theo rủi ro mất thông tin không gian/ngữ nghĩa, thay vì chỉ quay về lựa chọn V2-C. Có thể nghiên cứu đặc trưng từ một encoder 2D đóng băng làm proxy không dùng `mc3_18`, với ràng buộc giữ BD-rate của hai analyzer chính. Đây là giả thuyết, hiệu quả **CHƯA ĐO**; chọn identity nhiều hơn có thể làm mất lợi ích bitrate.
- **Protocol mới trước thử nghiệm mới:** chốt feature/grid/gate trên FIT/CAL, commit policy và manifest trước scoring, rồi dùng DEV mới và holdout nguồn chưa xem có bằng chứng disjoint. Kết quả V11 chỉ dùng để hình thành giả thuyết nghiên cứu kế tiếp. Không chỉnh V11 hoặc dùng lại holdout đã thấy như xác nhận mới; không nới gate gốc <−15%.

V11 là **negative development study** về một proxy cụ thể, chưa phải kết quả xác nhận độc lập hoặc đủ để tuyên bố phương pháp chuyển giao. Runtime đầy đủ sáu candidate + selection: **CHƯA ĐO** ở V11; timing trong raw record là đánh giá. H.264 V11, holdout mới và OD V11: **CHƯA ĐO**.

## 6. Provenance và tái kiểm toán

| Thành phần | Commit / SHA-256 |
|---|---|
| Preregistration commit | `00951bd52efeb3c64feb62254cef2aa484431e60` |
| Preregistration Git blob SHA-256 | `2dda253a7297566bc97ac8f7800f4e6d20c49d8ad8e51c30a6147a7bfb5328c8` |
| CAL policy freeze commit | `49fb15f6de86f09c6c0a845098cbbf199c405c03` |
| CAL freeze JSON SHA-256 | `280c926a65458a00b192ed1cd0a44e6b341ac6a4f049c96852d5b0e15a410a0e` |
| Selection / scoring worker commit | `f67391e22c2d9ec2d7be0d34bf307c7c02b5fd77` |
| Merge analysis base commit | `91ba5721ad6dc21657bb0e8f675df344b5c6e7ad` |
| Code fingerprint | `5eee253b68a62498eeaeb0b10bd8e463e60d9248145273f7f7286f257c0ad07f` |
| Source plan SHA-256 | `bb4b9aa245ff2d8b5f92cb1a45dedb65adfc8a664543878bb7b9cdb1486b421e` |
| DEV input SHA-256 | `2c48519cb06b7b4580302d629aa7267fe0e35e8fc6ca525d18fa39909114eca5` |
| DEV global selection SHA-256 | `e0489ac9e39347bc31ac8c57f3bcc71f9f3d72580f3d5d25be8c1266171cab01` |
| DEV source fingerprint | `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258` |
| Result JSON SHA-256 | `624f889efd3e21cef60cb6390b6a237e25f6b384f6887f0c02e73fe1d8514afe` |

Policy giữ nguyên `tau=0, slack=0.05, qp_mode=all`. [Result](../results/v11_spatial_dev/h265_result.json) chứa ID/SHA-256 từng nguồn, manifest bốn shard, toàn bộ đường cong và CI. [Gói audit](../results/v11_spatial_dev/README.md) giữ nguyên bốn archive Kaggle, log, helper và SHA-256 bên ngoài JSON. Python 3.12.13, Torch 2.10.0+cu128, TorchVision 0.25.0+cu128, NumPy 2.0.2, FFmpeg 4.4.2; suy luận CUDA, trọng số giống nhau ở bốn shard. Hash trạng thái từng analyzer có trong result/validation. Môi trường merge CPU local được [ghi riêng](../results/v11_spatial_dev/analysis_environment.json): Python 3.11.14, NumPy 2.4.6, cùng SHA-256 của ma trận resample tái dựng từ seed đã khóa. Không nhầm phiên bản merge với phiên bản đo GPU.

Mã selector/metric/bootstrap không đổi trong lượt đánh giá này. Bộ test toàn repo trước triển khai đạt **519 passed, 3 warnings**; [log đã commit](../results/v11_spatial_dev_launch/pytest.log). Lượt này kiểm toán dữ liệu, archive, sidecar, tính số học/đường cong và trạng thái Git; không chạy thêm thí nghiệm hoặc chọn lại policy.
