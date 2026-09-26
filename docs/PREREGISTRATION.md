# Preregistration — V2-C independent source holdout

**Trạng thái: bản dự thảo để duyệt. `PREREGISTRATION_LOCKED: false`.** Nguồn ứng viên đã được kiểm toán ở mức metadata; danh sách 1.000 source ID cuối chưa khóa. Không chạy bất kỳ đánh giá holdout nào cho đến khi các trường `CHƯA CHỐT` bên dưới được điền, kiểm toán và commit trước lượt đánh giá đầu tiên. Mọi thay đổi giao thức sau commit phải có amendment ghi thời điểm và lý do; không được dùng kết quả holdout để quyết định amendment.

## Câu hỏi và tiêu chí đặt trước

Đánh giá policy V2-C đã đóng băng, riêng cho H.264 và H.265, so với `identity128` trên nguồn video chưa tham gia phát triển hoặc đánh giá trước đây.

**Gate chính giữ nguyên từ V2:** ở ít nhất một codec, **cả** `r2plus1d_18` và `r3d_18` phải có point estimate BD-rate Top-1 **< −15%** và BD-accuracy > 0 so với `identity128`. Dấu `<` là nghiêm ngặt. Báo riêng guard cũ: minimum same-QP Top-1 gap ≥ −1 điểm phần trăm cho cả hai analyzer. CI không thay point estimate trong quyết định gate. BD-rate không xác định hoặc thiếu dữ liệu nghĩa là gate chưa được xác nhận.

`mc3_18` là analyzer chuyển giao: báo BD-rate, BD-accuracy và CI riêng. Không dùng nó để fit, chọn, hiệu chỉnh policy hoặc sửa gate chính. Tính độc lập ở đây chỉ có nghĩa `mc3_18` không tham gia quá trình tạo V2-C đã khóa; không khẳng định nó chưa từng xuất hiện trong bất kỳ nghiên cứu nào khác của project.

## Policy và xử lý video đã khóa

- Dùng nguyên trạng `configs/dual_codec_search_v2_frozen/{h264,h265}/`. Không fit hoặc chỉnh threshold trong nghiên cứu xác nhận này.
- SHA-256 **byte thực của file trong checkout Windows hiện tại**: H.264 `613506cb70ef01d1e0c45103a1a8f7ed43a82b6023e7dfc2b808f8d0f768a3df`; H.265 `0d39061a0b8de838c60553a6b112a40db4c64975ddea0f19137d6fda183fa2dc`.
- SHA-256 **sau chuẩn hóa CRLF thành LF**: H.264 `c1cc53880ec320c1f60951adcccd4045fb1ac8881ae3ddfa5d5741d662b82985`; H.265 `10a97a207506791e6cdf40b6cf30d9521ff97ba3d34a9201dae198f777f3fc1c`. Đây là loại hash mà `file_sha256()` trong `ops/dual_codec_search_confirm_1000.py` kiểm tra với `configs/dual_codec_search_v2_confirm_1000.json` để cùng nội dung cho kết quả giống nhau trên Windows và Linux. Manifest phải ghi rõ loại hash đang dùng; không gọi hash LF là hash byte thực của checkout Windows.
- SHA-256 của risk model được kiểm tra theo `configs/dual_codec_search_v2_confirm_1000.json`; SHA-256 config và commit code của lượt đánh giá sẽ ghi trong manifest.
- Mỗi clip: 16 frame RGB, stride 2, crop thời gian giữa, nguồn 128×128; sáu candidate hiện có; QP 30, 35, 40, 45, 50; H.264/H.265 preset `medium`; bpp chuẩn hóa theo nguồn 128×128.
- Cả ba analyzer nhận cùng stream đã giải mã ở mỗi video/QP. Nhãn chỉ được đọc để chấm Top-1 sau khi lựa chọn stream; selector không nhận nhãn hoặc dự đoán của `mc3_18`.

Không phát triển policy mới trong nghiên cứu xác nhận này. Nếu một policy khác được phát triển trên DEV trong tương lai, đó là nghiên cứu riêng với preregistration và holdout riêng; không được chọn nó dựa trên kết quả ở đây.

## Tập dữ liệu và khóa holdout

Nguồn ứng viên đã chốt ở mức phát hành: [Kinetics-400 validation chính thức do CVDF công bố](https://github.com/cvdfoundation/kinetics-dataset), annotation `val.csv` SHA-256 `358eaf47e7f80ebf9b17d49eb0635ad5e0fdab98a9cbd75ffdd2ee5d5e5b6944`, danh sách 20 archive SHA-256 `7c75bab47da18ba747e8bdd826bec9139672336fd3431caa71ff563473080e77`. Có 19.906 `youtube_id` duy nhất và không trùng 28.625 source ID trong hợp hai inventory lịch sử đã kiểm toán. `docs/HOLDOUT_SPLIT.md` và `configs/holdout_source_audit/` lưu cơ chế, fingerprint và giới hạn đối chiếu. Đây là holdout **tách video nguồn trong cùng họ Kinetics-400**, không phải chứng cứ chuyển miền sang dataset khác. UCF101, HMDB51 và Something-Something-v2 không được dùng trực tiếp cho gate Top-1 này nếu không có phép ánh xạ nhãn được chốt trước; hệ nhãn của chúng khác Kinetics-400.

Chỉ dùng ID nguồn để chia tập. Chuẩn hóa source ID từ ID video gốc; nếu không xác định đáng tin cậy ID nguồn, loại video trước khi chọn mẫu. Đối chiếu source ID và hash file với tất cả ID TRAIN/VAL/TEST, cache V1/V2 và danh sách từ các đánh giá lịch sử có thể truy hồi, gồm mẫu E4 đã dùng các thư mục Kinetics sibling. Không chấp nhận kiểm tra trùng clip key đơn thuần. Ghi rõ các kho lịch sử không truy hồi được và giới hạn còn lại của kiểm toán duplicate.

Sau khi loại trùng nguồn, kiểm tra file đọc được trước khi chốt mẫu. Xếp các source ID hợp lệ tăng dần theo `SHA256("v2c-holdout-20260927\0" + source_id)`; dùng 1.000 source ID đầu. Một video nguồn chỉ đóng góp một clip. Không cân bằng lớp bằng nhãn; không thay video dựa trên bitrate, Top-1 hoặc hình ảnh. Cùng 1.000 ID và cùng thứ tự được dùng cho hai codec và ba analyzer.

Danh sách 1.000 ID, số lượng loại trùng, fingerprint SHA-256 của danh sách ID đã sắp xếp, SHA-256 index và commit chốt: **CHƯA CHỐT**. Hai nghìn ID ứng viên đã được chốt chỉ từ source ID bằng salt `v2c-holdout-20260927` trước khi đọc nhãn; preflight archive đang kiểm tra byte và giải mã. `ops/lock_official_holdout.py` yêu cầu commit danh sách ID và SHA video **trước** khi nó cho phép tạo index nhãn; runner `ops/paper_holdout_confirm.py` yêu cầu commit bản preregistration có `PREREGISTRATION_LOCKED: true`, split và index khớp byte. Nếu không có đủ 1.000 nguồn hợp lệ hoặc không chứng minh được disjoint, kết quả holdout = **CHƯA ĐO**. Không thay bằng phần còn lại của TEST cũ hay một tập đã xem. `docs/HOLDOUT_SPLIT.md` sẽ ghi phương pháp, nguồn, số clip, fingerprint và bằng chứng disjoint; file này cùng bản preregistration đã hoàn chỉnh phải được commit trước đánh giá.

## Đối chứng và phép phân tích

Đối chứng chính: `identity128`. Đối chứng novelty cố định từ trước: `area96` và `area112`, mỗi biến thể dùng ở mọi clip và QP. Báo V2-C so với từng đối chứng bằng phép so sánh ghép cặp trực tiếp. Không chọn baseline sau khi xem TEST. Chỉ tuyên bố giá trị vượt giảm độ phân giải thuần nếu V2-C tốt hơn **cả** `area96` và `area112` ở cả hai analyzer chính trong cùng một codec; báo CI của từng so sánh.

Tính mean bpp và mean Top-1 cho từng QP từ toàn bộ video, sau đó tính BD-rate và BD-accuracy bằng `src/metrics/bd_rate.py` hiện hành. Gộp record của mọi shard trước khi dựng curve; không lấy trung bình BD-rate giữa các shard. Báo toàn bộ năm điểm curve, số lượt chọn candidate và minimum same-QP gap.

Bootstrap 2.000 lần, seed `20260924`, resample cả video nguồn có hoàn lại; mọi QP, codec, analyzer và arm của video đó giữ ghép cặp. Báo CI percentile 2,5–97,5%, số draw hợp lệ và không hợp lệ. Không sửa logic bootstrap hoặc BD-rate sau khi thấy kết quả để cải thiện số.

Phân tích chính gồm bốn phép đo: hai analyzer chính × hai codec. Hai baseline cố định và `mc3_18` là phân tích phụ được báo đầy đủ, kể cả kết quả bất lợi. Không chọn codec, baseline hoặc analyzer hậu nghiệm để đổi câu hỏi chính.

## Ranh giới replication và runtime

Hai JSON V2 cũ và phép đánh giá `mc3_18` trên fingerprint `aae3888f3ae34d08` là replication trên TEST đã xem. Chúng không được nhập chung với holdout mới và không tham gia bất kỳ lựa chọn nào cho nghiên cứu này. JSON `mc3_18` đã gộp hiện có ngoài repo phải được kiểm toán lại từ record, hash và manifest trước khi công bố trong `results/paper_mc3_v2_confirmed/`.

Benchmark runtime dùng clip DEV cố định bằng hash, cùng phần cứng cho hai arm và thứ tự arm cân bằng theo ID. Full arm tính mọi trial encode/decode, sinh candidate, suy luận encoder và lựa chọn; identity arm tính chi phí encode/decode identity-only. Ghi wall-time, peak RAM của cây tiến trình kể cả FFmpeg, peak GPU memory nếu dùng GPU, phiên bản FFmpeg/Torch, CPU/GPU, số clip, số QP, thời gian tuyệt đối và tỉ lệ overhead. Runtime không phải phép đo holdout.

OD COCO hiện là pilot 100 ảnh với intervention khác V2-C; không dùng để suy ra khả năng tổng quát của AR. Chỉ nâng mức bằng chứng nếu có phép đo toàn COCO val2017 được chốt trước khi chạy.

## Provenance và quy tắc báo cáo

Mỗi JSON có code commit, preregistration commit, SHA-256 config/policy/index, fingerprint nguồn, seed, bootstrap unit và requested/valid draws. SHA-256 của chính JSON kết quả nằm trong `SHA256SUMS.txt` cùng commit phát hành để tránh self-hash đệ quy. Giữ record và manifest gốc.

Nếu gate trượt, viết rõ **KHÔNG ĐẠT** và trình bày như nghiên cứu replication/negative. Nếu chưa có holdout hợp lệ hoặc lượt chạy chưa xong, viết **CHƯA ĐO**. Không suy đoán số, không sửa ngưỡng, không tuyên bố tổng quát hóa sang tập nguồn hay tác vụ chưa được kiểm chứng.
