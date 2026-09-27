# Xác nhận V2-C trên holdout nguồn mới

**Trạng thái: CHƯA ĐO. Gate holdout: CHƯA XÁC NHẬN.** [Tập 1.000 source video](HOLDOUT_SPLIT.md), [index nhãn](../configs/holdout_source_audit/index.json) và [preregistration](PREREGISTRATION.md) đã được khóa trước khi chấm. Chưa chạy mô hình trên holdout; sẽ chỉ chạy sau khi người dùng duyệt bản preregistration cuối. Fingerprint nguồn `ea86e9ba66b2fe3143a891619ae34ae036c7f065ea083f4b076b53263e9c668d`, SHA-256 index `f0f7bd7d56b3b5345886e5be6027c1b1958a9b74efd79ec464eaec096302ec57`.

| Codec | Analyzer | BD-rate Top-1 so với identity | CI 95%, 2.000 bootstrap theo video nguồn |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | CHƯA ĐO | CHƯA ĐO |
| H.264 | `r3d_18` | CHƯA ĐO | CHƯA ĐO |
| H.264 | `mc3_18` | CHƯA ĐO | CHƯA ĐO |
| H.265 | `r2plus1d_18` | CHƯA ĐO | CHƯA ĐO |
| H.265 | `r3d_18` | CHƯA ĐO | CHƯA ĐO |
| H.265 | `mc3_18` | CHƯA ĐO | CHƯA ĐO |

Gate chính giữ nguyên: ít nhất một codec có **cả** `r2plus1d_18` và `r3d_18` với BD-rate Top-1 **< −15%** và BD-accuracy > 0 so với `identity128`. Không thể kết luận ĐẠT hay KHÔNG ĐẠT từ ô chưa đo.

Các kết quả đã hoàn thành có phạm vi khác: [gói V2-C trên TEST cũ](../results/dual_codec_search_v2_confirm_1000/README.md), [replication `mc3_18` trên chính TEST đó](../results/paper_mc3_v2_confirmed/README.md) và [so sánh downscale cố định trên DEV](../results/paper_downscale_dev/README.md). Chúng không được gộp với holdout mới hoặc dùng để chọn lại policy.
