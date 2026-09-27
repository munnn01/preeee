# V4 holdout source audit

**Trạng thái hiện tại: chỉ khóa kế hoạch ID ứng viên; 1.000 video cuối, nhãn và mọi kết quả analyzer đều CHƯA CHỐT/CHƯA ĐO.** Bản này được tạo sau khi policy V4 đã khóa trong `configs/v4_frozen/manifest.json`, trước khi stream video hoặc đọc nhãn cho V4.

Nguồn là official CVDF Kinetics-400 validation, cùng annotation và danh sách 20 archive đã kiểm toán cho V2. SHA-256 annotation là `358eaf47e7f80ebf9b17d49eb0635ad5e0fdab98a9cbd75ffdd2ee5d5e5b6944`; SHA-256 danh sách archive là `7c75bab47da18ba747e8bdd826bec9139672336fd3431caa71ff563473080e77`. Code tạo plan nằm ở commit `944de5a24f75f2c65a23ffb03e66e036b73c18c2`. Chỉ cột `youtube_id` được dùng để xếp hạng; code không truy cập cột nhãn, không chạy codec/analyzer và không đọc kết quả V2 holdout.

Quy tắc đã khóa trong [PREREGISTRATION_V4.md](PREREGISTRATION_V4.md): loại mọi ID lịch sử V1/V2, 800 ID FIT/CALIBRATION/DEV và 1.000 ID holdout V2; xếp các ID còn lại theo `SHA256("v4-source-holdout-20260927\0" + source_id)`. Chọn 1.000 video đầu tiên có byte hợp lệ và đọc được trong thứ tự đó. Tập xác nhận là **source-disjoint trong Kinetics**, không phải kiểm tra chuyển miền. Kiểm toán ID không loại trừ chắc chắn một cảnh bị đăng lại với ID khác.

| Kiểm toán chỉ theo ID | Số lượng |
|---|---:|
| Official validation ID duy nhất | 19.906 |
| Inventory lịch sử hợp nhất | 28.625 |
| Giao official với inventory lịch sử | 0 |
| Giao official với 800 ID phát triển | 0 |
| Giao official với holdout V2 đã xem | 1.000, tất cả đã loại |
| ID official còn hợp lệ | 18.906 |
| Ứng viên đầu tiên theo hash để kiểm tra byte/giải mã | 2.000 |

[candidate_plan.json](../configs/v4_holdout_source_audit/candidate_plan.json) có SHA-256 `fb41bf70b65833cf5b48d27326731322b6250822554edd7b086e4957bde78c7e`; [candidate_ids.txt](../configs/v4_holdout_source_audit/candidate_ids.txt) có SHA-256 `2b07de362a2e6e07239da024106dfc6f498e4b4b2ea9cf696afd8aa79bbd1485`. Cả hai đã được commit tại `ffb7e2c5497dce23a42732e38910219086eea508` **trước khi stream video V4**. Fingerprint của tập 2.000 ID đã sắp xếp là `a8804ab6a1f390054f39303d4580f83e273dab3d20a4434ecded8c6357691368`. [Audit giao ID](../configs/v4_holdout_source_audit/prior_preflight_overlap.json) cho thấy trong 2.000 ứng viên có 104 ID từng được **preflight byte-only nhưng không được chọn vào V2 holdout**; giao với 1.000 ID V2 đã đánh giá bằng 0. Preflight byte-only không dùng nhãn hoặc kết quả model.

Chưa có fingerprint của 1.000 video hợp lệ cuối. Sau khi kiểm tra byte/giải mã, sẽ commit danh sách ID, SHA-256 từng video và bằng chứng disjoint **trước** khi code tạo index đọc nhãn. Nếu không có đủ 1.000 nguồn hợp lệ, kết quả V4 holdout là **CHƯA ĐO**. Không thay bằng clip TEST hoặc V2 holdout cũ.
