# Holdout source audit and split

**Trạng thái: đang kiểm tra giải mã; chưa khóa 1.000 clip, chưa chạy đánh giá holdout.** File này ghi phần kiểm toán ID đã hoàn tất. Phần danh sách video cuối, fingerprint và index sẽ được bổ sung bằng một commit **trước** khi chạy V2-C trên holdout.

## Nguồn ứng viên

Nguồn là [Kinetics-400 validation do CVDF phát hành](https://github.com/cvdfoundation/kinetics-dataset), dùng [annotation `val.csv`](https://s3.amazonaws.com/kinetics/400/annotations/val.csv) và [danh sách 20 video archive](https://s3.amazonaws.com/kinetics/400/val/k400_val_path.txt). Đây là nguồn Kinetics-400 có nhãn tương thích với ba analyzer hiện tại, **không phải** kiểm chứng chuyển miền sang UCF101/HMDB51/SSv2.

- Annotation CSV: 19.906 hàng, 19.906 `youtube_id` duy nhất; SHA-256 `358eaf47e7f80ebf9b17d49eb0635ad5e0fdab98a9cbd75ffdd2ee5d5e5b6944`.
- Danh sách 20 archive: SHA-256 `7c75bab47da18ba747e8bdd826bec9139672336fd3431caa71ff563473080e77`. Cả 20 URL trả HTTP 200 khi kiểm tra HEAD; tổng `Content-Length` là 30.354.517.239 byte (28,27 GiB). Điều này xác minh nguồn lưu trữ tồn tại, chưa chứng minh từng video giải mã được.
- Quy tắc ID: `youtube_id` trong CSV và 11 ký tự ID gốc trong tên file của các dataset cũ. Chọn mẫu bằng `SHA256("v2c-holdout-20260927\0" + source_id)`, chỉ dùng ID; không dùng nhãn, bitrate hoặc Top-1.

## Bằng chứng tách nguồn ở mức metadata

Kaggle API được phân trang đến trang cuối để lấy danh sách **toàn bộ file** của hai dataset từng dùng, không chỉ canonical TEST. Danh sách ID và hash kiểm toán đã lưu trong `configs/holdout_source_audit/`.

| Dataset lịch sử | File được liệt kê | Source ID duy nhất | ID trùng official K400 validation |
|---|---:|---:|---:|
| `qktttttttttt/kineticscleaned` | 10.844 | 10.800 | 0 |
| `rohanmallick/kinetics-train-5per` | 29.256 | 28.625 | 0 |

Toàn bộ 10.800 source ID của `kineticscleaned` nằm trong danh sách 28.625 ID của `kinetics-train-5per`. Vì vậy hợp hai nguồn lịch sử có 28.625 source ID; giao với 19.906 ID official validation bằng **0**. Điều này bao phủ canonical TRAIN/VAL/TEST, mẫu V1/V2 TEST fingerprint `aae3888f3ae34d08`, và các thư mục sibling của `kinetics-train-5per` từng được dùng trong đánh giá E4. Kiểm tra bằng source ID mạnh hơn kiểm tra `<class>/<filename>`; vẫn không thể loại trừ video bị đổi ID hoặc re-encode từ cùng cảnh khi không có toàn bộ byte/video lịch sử.

Danh sách ứng viên theo hash đầu tiên gồm 2.000 ID, lưu ở `configs/holdout_source_audit/official_val_candidate_ids.txt`; SHA-256 của tập ID sắp xếp là `b3dfc5ab1957c8fd9bf81b09dbdb369564159493585c2172c1b0f77b79cc8fb6`. `candidate_plan.json` ghi hash nguồn và code commit `6493418c54398b58b45118266d15155db3f85dc7`. Đây là **ứng viên để kiểm tra giải mã**, chưa phải tập TEST cuối. Nếu 2.000 ứng viên không cho đủ 1.000 video đọc được, trạng thái là **CHƯA ĐO** và giao thức phải được xử lý trước bất kỳ đánh giá nào; không thay bằng đuôi TEST cũ.

## Điều kiện còn thiếu trước khi mở holdout

1. Stream archive chính thức, giữ các video ứng viên theo ID, đối chiếu tên member với annotation và kiểm tra giải mã mà không chạy analyzer.
2. Chọn đúng 1.000 source ID đọc được đầu tiên trong thứ tự hash đã chốt; lưu tên clip, SHA-256 video, fingerprint danh sách 1.000 ID và index nhãn Kinetics-400 đã xác minh.
3. Commit `docs/PREREGISTRATION.md` đã điền đủ, file này và index/list cuối trước lượt đánh giá holdout đầu tiên. Sau commit đó mới chạy hai codec × ba analyzer một lần.

Các kết quả `mc3_18` trên TEST cũ và downscaling trên DEV không tham gia bước chọn 1.000 ID.
