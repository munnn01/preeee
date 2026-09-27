# Preregistration V4 — supervised label-free correctness selector

**Trạng thái: giao thức khóa trước khi viết mã V4 hoặc tính kết quả V4.** Nghiên cứu này được đề xuất sau [V3 không có policy mới](../results/v3_dev_policy/README.md) và [oracle dùng nhãn trên DEV](../results/v4_dev_oracle/README.md). Các kết quả đó chỉ định hướng giả thuyết, **không** là tập xác nhận. Kết quả V2 holdout đã công bố; nó, TEST V1/V2 và `mc3_18` không được đọc bởi script fit/chọn V4. Mọi xác nhận V4 đòi một holdout nguồn mới.

## Giả thuyết và gate không đổi

Sáu candidate hiện tại có thể tiết kiệm bit mà vẫn giữ các dự đoán đúng trên DEV; một selector **không dùng nhãn khi chạy** dự báo xác suất đúng của từng candidate có thể khai thác tốt hơn các ngưỡng risk V2/V3. Cùng 16 frame, stride 2, nguồn 128×128, QP `30,35,40,45,50`, preset `medium`, H.264/H.265, hai analyzer `r2plus1d_18`/`r3d_18` và sáu candidate V2. Không thêm transform ở vòng này; chi phí encoder đầy đủ vẫn là giới hạn phải báo.

**Gate holdout giữ nguyên:** ít nhất một codec có *cả* hai analyzer chính với point estimate BD-rate Top-1 **< −15%** và BD-accuracy > 0 so với `identity128`. Báo guard minimum same-QP Top-1 gap ≥ −1 điểm phần trăm. `mc3_18` chỉ là phân tích chuyển giao sau freeze, không dùng fit/chọn và không đổi gate. CI không thay point estimate. Không đạt thì ghi **KHÔNG ĐẠT**, chưa đo thì **CHƯA ĐO**.

## Dữ liệu phát triển và mô hình đã khóa

Dùng đúng cache pilot V2 gồm 400 source FIT, 200 CALIBRATION, 200 DEV cho mỗi codec, fingerprint tương ứng `4c12443af5c0ef44dc5143217ab00b146e0d9090607c49393487d5decd4e4bb1`, `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`, `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`. Ba phần source-disjoint và không trùng ID holdout V2. FIT/CALIBRATION/DEV đều là **tập phát triển**. Mỗi artifact ghi SHA-256 manifest/index/cache, source fingerprint, commit, seed và bootstrap unit. Không dùng outcome từ TEST hoặc holdout V2.

Trên FIT, tạo một hàng cho mỗi source × QP × candidate (400 × 5 × 6 = 12.000 hàng mỗi codec). Đầu vào là `risk_features(obs, candidate_index, qp)` hiện hành sau `observations()` đã xóa các trường outcome/nhãn. Đích là `correct` cho `r2plus1d_18` và `cross_correct` cho `r3d_18`. Fit **hai** `sklearn.ensemble.HistGradientBoostingClassifier` riêng theo codec, một cho mỗi analyzer: `loss="log_loss"`, `learning_rate=0.05`, `max_iter=100`, `max_leaf_nodes=15`, `min_samples_leaf=40`, `l2_regularization=1.0`, `early_stopping=False`, `random_state=53`, các tham số còn lại mặc định, sample weight bằng nhau cho mọi hàng. Không tune hyperparameter, feature hay model family sau khi xem CALIBRATION/DEV. Ghi version sklearn và SHA-256 mô hình đã xuất. Nếu một đích chỉ có một lớp hoặc feature không hữu hạn, dừng V4 thay vì thay model hậu nghiệm.

Khi chọn một stream, dự báo `P(correct)` cho identity và từng candidate bằng model tương ứng. Tính `delta_m = P_m(candidate correct) − P_m(identity correct)` cho hai analyzer. Candidate hợp lệ nếu bpp nhỏ hơn identity và `delta_m ≥ threshold_m` cho **cả hai**; identity luôn hợp lệ. Chọn candidate hợp lệ có bpp nhỏ nhất, tie-break theo thứ tự sáu candidate gốc. Không có nhãn, `correct`/`cross_correct` hoặc `mc3_18` trong hàm chọn stream. Dự báo xác suất chỉ dùng ở encoder; outcome chỉ đọc sau lựa chọn để chấm.

## Calibration, DEV và quy tắc thăng cấp

Chỉ trên 200 CALIBRATION, tìm ngưỡng riêng theo analyzer và nhóm QP: `low_r2`, `low_r3`, `high_r2`, `high_r3` đều trong `{-0.05, 0.00, +0.05}` (QP thấp ≤35, cao ≥40), đúng **81** policy. Một policy khả thi nếu trên cả hai analyzer BD-rate/BD-accuracy xác định, BD-rate <0, BD-accuracy >0 và minimum same-QP gap ≥ −1 điểm phần trăm. Chọn policy khả thi nhỏ nhất theo `max(BD-rate_r2, BD-rate_r3)`, rồi tổng hai BD-rate, rồi tuple ngưỡng tăng dần. V2-C frozen là comparator, không nằm trong lưới V4.

Chỉ thăng cấp **V4 candidate** theo từng codec nếu worst BD-rate CALIBRATION tốt hơn V2-C ít nhất **1,00 điểm phần trăm**, và BD-rate từng analyzer không kém V2-C quá **0,50 điểm phần trăm**. Codec không đạt dùng V2-C fallback. Nếu cả hai fallback, báo toàn bộ grid và dừng trước holdout. Không thay margin hoặc chọn theo DEV/TEST/holdout.

Sau freeze trên CALIBRATION, đánh giá 200 source DEV **một lần**: V4 candidate/fallback, V2-C và identity; năm điểm curve, BD-rate, BD-accuracy, same-QP gap, choice counts và CI percentile 95% với **2.000 bootstrap theo source video**, seed `20260928`. So sánh V4 với V2-C trực tiếp trên cùng video/QP. Go/no-go cho lượt xác nhận đắt tiền: ít nhất một codec có V4 candidate mới, BD-rate V4 so với identity tốt hơn V2-C trên **cả hai** analyzer, BD-accuracy V4 >0 và guard đạt. Go/no-go chỉ quyết định chi phí, **không** thay gate < −15% trên holdout. Không chỉnh model/ngưỡng theo DEV; nếu không đạt, công bố DEV exploratory và không mở holdout.

## Holdout V4 một lần nếu qua go/no-go

Lấy source ID từ official CVDF Kinetics-400 validation, trừ mọi source ID lịch sử V1/V2, FIT/CALIBRATION/DEV và 1.000 ID holdout V2. Xếp theo `SHA256("v4-source-holdout-20260927\0" + source_id)`. Chọn 1.000 source đầu tiên có video byte hợp lệ/giải mã được; preflight chỉ dùng ID/video, không dùng nhãn, bitrate, Top-1 hoặc ảnh để thay mẫu. Commit **ID, SHA-256 từng video và fingerprint trước khi đọc nhãn/tạo index**. Nguồn này tách ID trong cùng Kinetics; không gọi là external-domain. Nếu không khóa đủ 1.000 nguồn hợp lệ hoặc không chứng minh được disjoint, ghi **CHƯA ĐO**.

Sau khi policy/model V4 và index đã freeze/commit, chạy **một lần** trên 1.000 source mới, hai codec, hai analyzer chính và `mc3_18` độc lập. Báo V4, V2-C, identity, `area96`, `area112`; V2-C và V4 đều chọn từ đúng sáu candidate đã mã hóa. Với `mc3_18`, chấm identity và stream V4 đã chọn, không dùng nó để chọn. Gộp hai shard 500 trước khi dựng curve; bootstrap 2.000 lần theo source video, seed `20260928`, mọi QP/arm/analyzer/codec ghép cặp. Công bố toàn bộ kết quả kể cả bất lợi, hash config/index/raw/result và commit. Không dùng lại holdout V2 để hiệu chỉnh V4. Một policy phát triển sau khi thấy holdout V4 phải có holdout khác nữa.
