# Chi phí runtime của V2-C

Đã đo trên **20 clip DEV cố định**, mỗi clip gồm 16 frame và năm QP `30,35,40,45,50`. Đây là phép đo chi phí, không phải đánh giá holdout. Mẫu được chọn bằng salt `paper-runtime-v1-20260924`; fingerprint source ID là `22e6fde29d8629ed726745b9be05f211b3528239899a8198768c37270ccbc834`. Kiểm tra SHA-256 video đầu vào đạt **20/20**; [manifest kiểm tra nguồn](../results/paper_runtime_v2_full/runtime_input_check.json), [danh sách mẫu](../configs/paper_runtime_dev/sample_ids.json) và [index thực thi](../results/paper_runtime_v2_full/kaggle_index.json) cho phép kiểm tra lại.

## Phép đo và kết quả

`identity` thực hiện năm lần encode/decode, một lần tại mỗi QP. `full` tạo sáu candidate và thực hiện đủ **30 lần encode/decode** trên mỗi clip, chạy hai analyzer phía encoder và chọn stream theo V2-C. Hai arm chạy trong tiến trình riêng; thứ tự được cân bằng theo clip bằng salt `paper-runtime-order-20260924`. Wall-time gồm mọi lần gọi FFmpeg, sinh candidate và suy luận phía encoder; không gồm tải trọng số hay khởi tạo tiến trình. Tỉ lệ dưới đây là **trung vị của 20 tỉ lệ ghép cặp theo clip**, không phải tỉ số của hai trung vị thời gian.

| Codec | Clip DEV | Identity, trung vị giây/clip | Full, trung vị giây/clip | Overhead thời gian, trung vị | Peak RSS identity → full, trung vị GiB | JSON nguồn |
|---|---:|---:|---:|---:|---:|---|
| H.264 | 20 | 1.558 | 11.418 | 7.351× | 0.744 → 1.151 | [h264_result.json](../results/paper_runtime_v2_full/h264_result.json) |
| H.265 | 20 | 1.752 | 12.682 | 7.066× | 0.760 → 1.163 | [h265_result.json](../results/paper_runtime_v2_full/h265_result.json) |

Trung bình theo clip: H.264 `identity=1.591 s`, `full=11.497 s`, tỉ lệ ghép cặp `7.252×`; H.265 `identity=1.798 s`, `full=12.677 s`, tỉ lệ `7.072×`. Peak RSS là tổng cây tiến trình worker và các tiến trình FFmpeg, lấy mẫu mỗi **5 ms**; vì vậy peak ghi nhận là **cận dưới**. Median peak GPU reserved của full arm là **422 MiB** cho mỗi codec, xem từng record trong JSON. Bộ nhớ GPU là chỉ số riêng, không cộng vào RSS. Chưa đo độ trễ triển khai streaming hoặc throughput trên hệ thống sản xuất; các số này không chứng minh khả năng thời gian thực.

## Máy, phiên bản và truy vết

Notebook riêng tư chạy cả hai codec trên cùng máy Kaggle: **Tesla T4**, CPU `x86_64` **4 logical cores**, RAM **33,659,383,808 bytes**. Python `3.12.13`, PyTorch `2.10.0+cu128`, TorchVision `0.25.0+cu128`, FFmpeg `4.4.2-0ubuntu0.22.04.1`; `torch_num_threads=2`. Execution commit `c7c5f92b73d60b7f0679b0e9b2d3919ec1037913`; packaging commit `3139022ec68ad639a6c76b94b0f18a76b50e7c07`. Kết quả chỉ mô tả đúng máy và mẫu này.

SHA-256 index `1a7adb6ad3aac2fa3fc93767c9567e49441b35f7ad6375fe7e1949ef0507acb2`; SHA-256 danh sách mẫu `3e6e1dd4570b702bb3e0dddc9d25e9afb1c1faa043b6dab9099e7f53f58f740e`; SHA-256 config chuẩn hóa LF trong cả hai JSON `7161844038eb90a6ad3c2739865736484643249c50cc4cc648cafddf287232c0`. Hash của **file config Windows nguyên byte** được khóa riêng trong [preregistration](PREREGISTRATION.md), vì CRLF/LF cho hash khác nhau. [Provenance](../results/paper_runtime_v2_full/provenance.json) và [SHA256SUMS](../results/paper_runtime_v2_full/SHA256SUMS.txt) khóa toàn bộ gói: H.264 result `83b47179cd2d986149b43fde6adc1ec191caae356eb6bb262ee078e11f2090c0`, H.265 result `017bb4b6d4da3ef5cb41e1f5872ff353afa7cb17bc9c8f25ad43f3b6c0030ad0`.

Runtime là thống kê mô tả, **không bootstrap** (`bootstrap_draws=0`); đơn vị đo là source clip DEV. Không dùng bộ sinh số ngẫu nhiên để chọn mẫu hay sắp thứ tự arm (`random_seed=null` trong provenance); hai salt SHA-256 cố định được ghi ở trên. Các khoảng CI về BD-rate được tính trong thí nghiệm chất lượng riêng, với đơn vị bootstrap là source video.
