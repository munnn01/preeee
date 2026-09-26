# Chi phí runtime của V2-C

**Trạng thái: CHƯA ĐO** cho benchmark đầy đủ năm QP trên cùng một máy. Không dùng phép đo QP 40 cũ để suy ra thời gian hay bộ nhớ của toàn bộ quá trình chọn stream.

## Giao thức đã khóa

`ops/paper_runtime.py` chạy trên clip DEV được chọn bằng hash ID, với thứ tự hai arm cân bằng theo clip. `identity` thực hiện năm lần encode/decode, một lần tại mỗi QP `30,35,40,45,50`. `full` tạo sáu candidate, thực hiện đủ 30 lần encode/decode, chạy hai analyzer ở phía encoder trên candidate đã giải mã, tính tín hiệu chọn và chọn stream. Hai arm chạy trong tiến trình riêng để bộ nhớ của model không bị cộng vào đối chứng identity. Thời gian wall-clock và peak RSS của cây tiến trình (gồm FFmpeg) được ghi theo clip; RSS được lấy mẫu mỗi 5 ms nên peak báo cáo là **cận dưới lấy mẫu**. Nếu dùng GPU, ghi thêm peak memory do PyTorch cấp phát.

Benchmark sẽ báo cho **cả H.264 và H.265**: cấu hình CPU/GPU, Python/Torch/FFmpeg, commit và SHA-256 config/index, fingerprint clip DEV, seed, số clip, thời gian tuyệt đối cho từng arm, tỉ lệ overhead, peak memory và số codec call thực tế. JSON và hash kết quả sẽ đặt trong `results/paper_runtime_v2_full/`.

| Codec | Clip DEV | Identity (giây/clip) | Full (giây/clip) | Tỉ lệ thời gian | Peak memory | JSON |
|---|---:|---:|---:|---:|---:|---|
| H.264 | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO |
| H.265 | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO |

Không tính chi phí tải trọng số và khởi tạo tiến trình vào thời gian theo clip; các bước này được ghi riêng trong manifest của runner. Chưa có kết luận thực nghiệm về tính khả dụng thời gian thực.
