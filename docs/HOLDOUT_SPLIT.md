# Holdout source audit and split

**Trạng thái: 1.000 source video đã khóa theo ID trong commit `c12f422ed85f8a4a61319fe169724c115f663f74`; index nhãn đã tạo và chưa chạy đánh giá holdout.** Danh sách và SHA video được commit trước khi mã tạo index đọc nhãn. Bản preregistration hoàn chỉnh và index được commit cùng bản cập nhật tài liệu này, trước lượt đánh giá đầu tiên.

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

Danh sách ứng viên theo hash đầu tiên gồm 2.000 ID, lưu ở `configs/holdout_source_audit/official_val_candidate_ids.txt`; SHA-256 của tập ID sắp xếp là `b3dfc5ab1957c8fd9bf81b09dbdb369564159493585c2172c1b0f77b79cc8fb6`. `candidate_plan.json` ghi hash nguồn và commit lập kế hoạch ban đầu `6493418c54398b58b45118266d15155db3f85dc7`. Đây là ứng viên để kiểm tra giải mã, không phải tập TEST cuối.

## Kết quả kiểm tra video và khóa ID

Đã stream đủ **20/20 archive chính thức**, tổng **30.354.517.239 byte nén**, tính SHA-256 trên từng luồng archive và giữ lại **1.998/2.000** video ứng viên. [Manifest của 20 archive](../configs/holdout_source_audit/archive_parts/) ghi SHA-256 của archive và từng video được giữ; [SHA256SUMS](../configs/holdout_source_audit/archive_parts/SHA256SUMS.txt) của các manifest có SHA-256 `18c42aaa54d04ce8c5440491acb9211814cf031fc20e20d32dd88347e5ded188`. Tất cả 1.000 video được chọn xuất hiện **đúng một lần** trong manifest archive với cùng kích thước và SHA-256. Hai ID trước mốc chọn thứ 1.000 không có video đọc được; chúng được ghi cùng lý do trong [preflight_selection.json](../configs/holdout_source_audit/preflight_selection.json).

Lần kiểm tra cuối chạy bằng code commit `2fd930cb5273d516b461791b395b46689b778fdb`; SHA-256 [preflight_selection.json](../configs/holdout_source_audit/preflight_selection.json) là `caeb697bce1c561ccc57242356e48ceb54510431077da9ac787a5825305c465f`. Bản kiểm tra ban đầu có cùng **toàn bộ 1.000 record được chọn và danh sách thất bại**; lần cuối được chạy lại để manifest chỉ commit code đã chứa bản vá retry mạng. Lượt này chỉ đọc ID, byte video và frame đầu để kiểm tra giải mã, không đọc nhãn hay chạy analyzer.

Quy tắc đã chốt chọn **1.000 source ID đầu tiên đọc được trong thứ tự hash**, mỗi source đúng một video. Fingerprint SHA-256 của tập ID đã sắp xếp: `ea86e9ba66b2fe3143a891619ae34ae036c7f065ea083f4b076b53263e9c668d`. SHA-256 [selected_ids.txt](../configs/holdout_source_audit/selected_ids.txt) là `7f4d583812cd0bc20335aeaf2f62520ad8a9c32aa8c3f7d591df39c2a1852bc4`; SHA-256 [selected_sources.json](../configs/holdout_source_audit/selected_sources.json) là `5509f8b766a9c3a51b4d8cbe2838bb62e5bbf7088d8875ce028126913d92d9f0`. Hai file này chứa ID, tên và hash video, **không chứa nhãn**. Giao của 1.000 ID với hợp 28.625 ID lịch sử bằng **0** vì chúng được chọn từ tập eligible đã trừ toàn bộ inventory và giao nguồn chính thức với các inventory cũng bằng 0.

Sau commit ID-only `c12f422ed85f8a4a61319fe169724c115f663f74`, `ops/lock_official_holdout.py index` mới đọc annotation và tạo [index.json](../configs/holdout_source_audit/index.json) gồm đúng 1.000 record, path tương đối `videos/<filename>`, nhãn Kinetics-400 và SHA-256 từng video. SHA-256 index `f0f7bd7d56b3b5345886e5be6027c1b1958a9b74efd79ec464eaec096302ec57`. Builder xác nhận nhãn có trong cùng thứ tự 400 lớp của `r2plus1d_18`, `r3d_18` và `mc3_18`, tên file khớp ID/khoảng thời gian annotation, và byte video khớp manifest đã commit. Chưa suy luận analyzer trên bất kỳ video holdout nào.

Đây là **source-disjoint trong cùng họ Kinetics-400**, không phải external-domain holdout. Kiểm toán theo ID không loại trừ một cảnh bị đổi ID hoặc re-encode trong kho lịch sử; thiếu byte đầy đủ của mọi video lịch sử nên không tuyên bố chắc chắn ở mức cảnh. Không dùng nhãn để cân bằng lớp và không thay clip theo bitrate hay kết quả Top-1.

## Điều kiện còn thiếu trước khi mở holdout

1. Người dùng duyệt bản `docs/PREREGISTRATION.md` cuối đã commit, gồm commit khóa ID và SHA-256 index ở trên.
2. Sau khi được duyệt, chạy hai codec × ba analyzer đúng một lần theo giao thức đã khóa; không dùng kết quả để thay policy, tập, đối chứng hay gate.

Các kết quả `mc3_18` trên TEST cũ và downscaling trên DEV không tham gia bước chọn 1.000 ID.
