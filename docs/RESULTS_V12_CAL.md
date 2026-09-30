# V12-A spatial: kết quả CAL

**PASS gate sàng lọc CAL; trạng thái `FREEZE_BEFORE_NEW_DEV_PROTOCOL`. Gate nghiên cứu gốc −15%: KHÔNG ĐẠT trên CAL. Mục tiêu đầy đủ ba analyzer, mc3_18, DEV mới và holdout: CHƯA ĐO.** Đây là phép phát triển trên CAL đã dùng; CI sau chọn policy chỉ mô tả, chưa hiệu chỉnh bất định do lựa chọn.

Đã xác minh 4/4 job COMPLETE phiên bản v1, đủ 200 nguồn/1.000 source-QP observations và 2235 trial encode/decode. Tất cả 2.235 stream trùng giữa hai hướng có cùng số byte và SHA-256 pixel decode. Hai analyzer chính dùng correctness trong index CAL lịch sử đã khóa; worker chỉ đo proxy/codec, không chạy AR inference mới. [JSON kết quả](../results/v12_lowqp/calibration_result.json), [phân tích mô tả](../results/v12_lowqp/assessment.json), [freeze](../results/v12_lowqp/frozen_policy.json).

## Policy được chọn và điều kiện

Policy `{"tau_relative": 0.5, "rate_slack": 0.5, "qp_mode": "lowmid"}`; 10/24 cấu hình khả thi, 88/1.000 lựa chọn đổi so với V6 trên 74/200 nguồn. QP 45/50 giữ V6. Lựa chọn theo ranking đã preregister: proxy reduction lớn nhất trong tập feasible của riêng hướng này, rồi các tie-break đã khóa. Không so sánh độ lớn proxy reduction giữa hai hướng vì hai proxy có ý nghĩa khác nhau.

CAL feasible: mỗi primary BD-rate <−10%, BD-accuracy >0, worst same-QP gap ≥−1 pp so với identity, rate không kém V6 quá 2 pp và proxy reduction >1e−6. Chính sách được chọn còn có đủ 2.000/2.000 draw hợp lệ cho BD-rate/BD-accuracy ở mọi comparator. Gate gốc và gate tương lai ba analyzer giữ nguyên.

## Đường cong gộp so với identity

| Analyzer | BD-rate % [CI95] vs identity | BD-accuracy pp [CI95] | Worst same-QP gap pp vs identity | Valid rate draws |
| --- | --- | --- | --- | --- |
| r2plus1d_18 | -13.43 [-16.74; -9.68] | +9.87 [+7.47; +12.35] | +2.00 | 2000 |
| r3d_18 | -13.13 [-15.98; -10.45] | +8.86 [+6.92; +10.99] | +0.50 | 2000 |

Khoảng CI của R2 vẫn vượt −10% về phía ít âm hơn. Vì đây là CAL đã dùng để chọn policy, CI không xác nhận mức tiết kiệm trên dữ liệu mới. Worst same-QP gap trong bảng này neo identity; bảng dưới neo từng comparator riêng.

## Comparator ghép cặp trên cùng CAL

| Anchor | Analyzer | Direct BD-rate % [CI95] | BD-accuracy pp [CI95] | Worst same-QP gap pp |
| --- | --- | --- | --- | --- |
| v6 | r2plus1d_18 | +0.93 [+0.48; +1.67] | -0.48 [-1.25; +0.26] | +0.00 |
| v6 | r3d_18 | +1.69 [+0.74; +2.61] | -1.10 [-1.93; -0.32] | -1.50 |
| area112 | r2plus1d_18 | -12.37 [-15.86; -9.23] | +10.77 [+8.17; +13.24] | +9.00 |
| area112 | r3d_18 | -6.88 [-9.83; -3.73] | +4.08 [+1.89; +6.44] | +2.50 |

Cả hai primary có BD-rate trực tiếp so với V6 dương với CI hoàn toàn dương: policy trả một phần hiệu quả rate–accuracy của V6 để bảo vệ proxy. Suy giảm BD-accuracy và thay đổi Top-1 được báo đầy đủ. Cả hai vẫn tốt hơn fixed area112 trên CAL; điều đó cho thấy selector có giá trị vượt baseline downscaling cố định trong phạm vi CAL, chưa phải bằng chứng tổng quát hóa.

## Thay đổi theo QP

| QP | Switches / 200 | Bpp change vs V6 % | R2 wins / losses vs V6 | R3 wins / losses vs V6 |
| --- | --- | --- | --- | --- |
| 30 | 62 | +10.212 | 0 / 0 | 0 / 3 |
| 35 | 24 | +3.611 | 1 / 1 | 1 / 1 |
| 40 | 2 | +0.107 | 0 / 0 | 0 / 0 |
| 45 | 0 | +0.000 | 0 / 0 | 0 / 0 |
| 50 | 0 | +0.000 | 0 / 0 | 0 / 0 |

Wins/losses là chuyển đúng/sai trong primary index lịch sử, so với V6 trên 200 nguồn, không phải quan sát MC3. QP 45/50 không đổi; deficit downstream tại các QP đó, nếu xuất hiện trên dữ liệu mới, sẽ không được cơ chế này sửa.

## Chi phí đã đo và phần còn thiếu

Tổng internal encode/decode timers qua bốn máy: 867.087 s; source + decoded proxy timers: 41.260 s, trung bình 0.2063 s/video cho toàn bộ năm QP đã chạy. Đây là tổng thời gian các vòng đo pilot, không phải elapsed wall-time của bốn job song song hay overhead đầy đủ của selector V6. Source I/O, model startup/download, inference của selector V6, peak memory và benchmark máy chuẩn chưa được đo trong pilot này.

V12-A chạy proxy CPU; V12-B dùng ResNet18 GPU. Môi trường hai hướng khác CPU/CUDA nên các internal timers không phải phép so sánh tốc độ được kiểm soát. Số trial pilot cũng không thể dùng làm tỷ lệ overhead encoder triển khai: cả hai sẽ cần chi phí lựa chọn V6 trong pipeline đầy đủ.

MC3 đã được quan sát trong các phiên bản trước và thúc đẩy giả thuyết V12; việc fit/chọn của V12 loại trừ MC3. Không tuyên bố đây là kiến trúc hoàn toàn chưa từng nhìn thấy.

Kiểm toán kết quả và 19 test V12 hiện tại đều PASS. [Record kiểm tra và test](../results/v12_lowqp_validation.json).

## Hướng tiếp theo

Commit hai policy và toàn bộ CAL choices trước bước tiếp theo. Ưu tiên V12-A cho đánh giá phát triển tiếp vì cơ chế đơn giản và point estimate trên primary tốt hơn; giữ V12-B làm comparator. Đây là lựa chọn nghiên cứu dựa trên CAL, chưa có kiểm định ghép cặp A/B preregistered hay bằng chứng MC3. Một protocol mới phải khóa fresh DEV source-disjoint, hai policy và các gate trước khi đo ba analyzer; mọi lựa chọn phải freeze trước inference. Gate đầy đủ kiểm tra MC3 <0, upper CI ≤+1%, mọi worst same-QP gap ≥−1 pp. Holdout mới phải khóa riêng và chỉ đánh giá một lần ở cuối.

## Toàn bộ lưới đã đăng ký

| tau | slack | QP mode | R2 BD-rate % | R3 BD-rate % | R2 worst gap pp | R3 worst gap pp | Proxy reduction (own scale) | Switches | CAL feasible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 0.1 | low | -13.3418 | -14.0493 | 1.50 | 0.50 | 0.00463326 | 38 | True |
| 0.0 | 0.1 | lowmid | -11.6937 | -12.7176 | 1.00 | 0.50 | 0.01320436 | 95 | False |
| 0.0 | 0.25 | low | -10.6208 | -11.5893 | -0.50 | 0.50 | 0.02729411 | 197 | False |
| 0.0 | 0.25 | lowmid | -7.0367 | -7.3597 | -0.50 | 0.50 | 0.04939280 | 327 | False |
| 0.0 | 0.5 | low | -8.5398 | -7.7727 | 0.00 | -0.50 | 0.05866067 | 353 | False |
| 0.0 | 0.5 | lowmid | -4.5711 | -2.7587 | 0.00 | -0.50 | 0.08171036 | 487 | False |
| 0.1 | 0.1 | low | -13.3440 | -14.0528 | 1.50 | 0.50 | 0.00456316 | 37 | True |
| 0.1 | 0.1 | lowmid | -11.6968 | -12.9012 | 1.00 | 0.50 | 0.01306361 | 93 | False |
| 0.1 | 0.25 | low | -10.6231 | -11.5926 | -0.50 | 0.50 | 0.02722400 | 196 | False |
| 0.1 | 0.25 | lowmid | -7.0397 | -7.5976 | -0.50 | 0.50 | 0.04925205 | 325 | False |
| 0.1 | 0.5 | low | -8.5420 | -7.7758 | 0.00 | -0.50 | 0.05859057 | 352 | False |
| 0.1 | 0.5 | lowmid | -4.5740 | -3.0450 | 0.00 | -0.50 | 0.08156961 | 485 | False |
| 0.25 | 0.1 | low | -13.8642 | -14.0715 | 1.50 | 0.50 | 0.00339926 | 27 | True |
| 0.25 | 0.1 | lowmid | -13.3999 | -13.3194 | 1.50 | 0.50 | 0.00847201 | 58 | True |
| 0.25 | 0.25 | low | -11.5700 | -11.6839 | -0.50 | 0.50 | 0.02515975 | 179 | False |
| 0.25 | 0.25 | lowmid | -9.6408 | -8.8500 | -0.50 | 0.50 | 0.03958719 | 257 | False |
| 0.25 | 0.5 | low | -9.7712 | -7.8614 | 0.50 | -0.50 | 0.05652631 | 335 | False |
| 0.25 | 0.5 | lowmid | -7.6197 | -4.3823 | 0.50 | -0.50 | 0.07190475 | 417 | False |
| 0.5 | 0.1 | low | -14.0482 | -14.4829 | 2.00 | 0.50 | 0.00025013 | 1 | True |
| 0.5 | 0.1 | lowmid | -14.0420 | -14.4773 | 2.00 | 0.50 | 0.00051552 | 2 | True |
| 0.5 | 0.25 | low | -13.9773 | -14.2010 | 2.00 | 0.50 | 0.00448479 | 22 | True |
| 0.5 | 0.25 | lowmid | -13.9476 | -14.1746 | 2.00 | 0.50 | 0.00513787 | 24 | True |
| 0.5 | 0.5 | low | -13.4627 | -13.1529 | 2.00 | 0.50 | 0.02086545 | 86 | True |
| 0.5 | 0.5 | lowmid | -13.4329 | -13.1263 | 2.00 | 0.50 | 0.02151853 | 88 | True |

## Truy xuất và provenance

| Artifact / scope | Value |
| --- | --- |
| Analysis commit | `47e4eb3dd4f7d8ed9619e0d2e6b20a3fcecc16cb` |
| Worker commit | `17cc33f81a1d685574dc1a11956b12f89b1b59ab` |
| Preregistration commit | `1a734e9228644c1cf13deeb517995593d295fb8a` |
| Source fingerprint | `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721` |
| CAL input SHA-256 | `db9fd6eef315657b33f9e0d557260c7af2a89857633193e6d41c83b056a7983d` |
| Primary index SHA-256 | `35b42f2874e909fddfc38363c6d0b47ef8a5e85abfcc4adcbea40eaaabb4150d` |
| Result SHA-256 | `2bd161d4b18f6f78ea85edeb9987079bd832e67d3b9e7e04b837a5bd6af81d1d` |
| Bootstrap unit | source video; all QPs, arms and primary analyzers paired |
| Bootstrap seed / draws | 20261009 / 2000 |
| Worker Python / Torch / Torchvision | 3.12.13 / 2.10.0+cpu / 0.25.0+cpu |

Archive, records, manifest và log gốc được giữ trong `results/v12_lowqp/raw/shardN/`; artifact manifest chứa SHA-256 của toàn bộ file. Metric BD-rate và logic bootstrap không đổi. Mỗi số trong báo cáo được lưu trong calibration_result.json hoặc assessment.json.
