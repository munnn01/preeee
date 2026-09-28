# V6: kết quả phát triển trên cache FIT/CAL/DEV cũ

Notebook Kaggle riêng tư [shungg05/v6-dev-residual-db57f13](https://www.kaggle.com/code/shungg05/v6-dev-residual-db57f13) hoàn tất bằng code commit `db57f13fcc7acd72f5c7f90f316134ebaf1ec48f`, sau [preregistration V6](PREREGISTRATION_V6.md) commit `efdf5e3d7bd0889c6dc09bc05dc12c928ffb1159`. Artifact gốc, các JSON, mô hình và SHA-256 nằm trong [gói kết quả](../results/v6_dev_residual/README.md). Mọi số dưới đây lấy từ [JSON H.264](../results/v6_dev_residual/results/h264_result.json) hoặc [JSON H.265](../results/v6_dev_residual/results/h265_result.json); không suy ra kết quả cho analyzer chưa chấm.

Trên CAL, lưới đã khóa có 12 policy mỗi codec. H.264 có **3/12** policy hợp lệ, chọn `minimum_expected_delta=-0.05`, `feature_weight=80`. H.265 có **4/12**, chọn `-0.05`, `20`. Hai policy được chọn trên CAL rồi mới chấm DEV. Quy tắc CAL yêu cầu BD-rate Top-1 của từng analyzer chính không kém V2-C quá 1,00 điểm phần trăm, BD-accuracy >0, worst same-QP Top-1 gap ≥−1,00 điểm phần trăm, đồng thời giảm mean source-feature distance. Không thay ngưỡng sau khi xem kết quả.

| Codec | Analyzer chính | V2-C DEV: BD-rate so với identity | V6 DEV: BD-rate so với identity, CI 95% | V6 so với V2-C trực tiếp, CI 95% |
|---|---|---:|---:|---:|
| H.264 | `r2plus1d_18` | −20,40% | −18,59% [−22,92%; −14,27%] | **+2,31%** [+0,17%; +4,44%] |
| H.264 | `r3d_18` | −11,42% | −12,59% [−16,42%; −9,46%] | −1,22% [−3,46%; +1,10%] |
| H.265 | `r2plus1d_18` | −14,87% | −16,26% [−19,31%; −12,88%] | **−1,75%** [−3,18%; −0,31%] |
| H.265 | `r3d_18` | −8,60% | −10,69% [−13,02%; −8,00%] | **−2,19%** [−3,70%; −0,41%] |

Các cột so với V2-C dùng **đường cong ghép cặp trực tiếp**; không trừ hai BD-rate ở cột trước. CI percentile 95% dùng 2.000 bootstrap theo **source video**, seed `20260930`, giữ QP, arm và hai analyzer ghép cặp. BD-accuracy V6 so với identity đều dương: H.264 lần lượt +8,32 và +4,77 điểm phần trăm; H.265 +11,63 và +6,25. Các curve đầy đủ và CI BD-accuracy nằm trong JSON.

**DEV go/no-go: H.264 KHÔNG ĐẠT; H.265 ĐẠT.** H.264 kém V2-C 1,81 điểm phần trăm BD-rate trên `r2plus1d_18`, vượt giới hạn +1,00, và worst same-QP gap của `r3d_18` là −1,50 điểm phần trăm, dưới ngưỡng −1,00. Không sửa policy H.264 theo DEV. H.265 cải thiện BD-rate trên cả hai analyzer chính, BD-accuracy dương và worst same-QP gap lần lượt +1,00 và 0,00 điểm phần trăm. Go/no-go chỉ cho phép **đề xuất** một xác nhận mới; riêng trên DEV, `r3d_18` H.265 đạt −10,69%, nên chưa đạt ngưỡng <−15% của gate xác nhận chính.

Mean source-feature distance H.265 giảm từ 0,017525 (V2-C) xuống 0,016055 (V6); hiệu ghép cặp −0,001470, CI 95% [−0,001815; −0,001155]. H.264 cũng giảm proxy, nhưng trượt điều kiện primary nói trên. Proxy này được tính từ hai analyzer dùng để phát triển; **chưa được xác nhận là dự báo lợi ích cho `mc3_18`**.

**V6 trên `mc3_18`: CHƯA ĐO. V6 trên holdout mới: CHƯA ĐO.** V4 và kết quả `mc3_18` cũ đã được xem trước V6. FIT/CAL/DEV cũng đã dùng qua nhiều vòng, nên kết quả trên DEV là exploratory, không chứng minh chuyển giao hay tổng quát hóa. Một nghiên cứu xác nhận cần khóa policy, mô hình, source-disjoint holdout và phân tích trong preregistration riêng trước lượt chấm. Gate cũ trên cả hai analyzer chính ở ít nhất một codec vẫn giữ nguyên.
