# pre_processor — nén hướng nhiệm vụ cho Action Recognition và Object Detection

Repo này nghiên cứu can thiệp miền pixel **trước codec chuẩn** để giảm bitrate mà vẫn giữ hiệu năng tác vụ. Hai đường đánh giá độc lập:

- **AR / Kinetics:** chọn một trong sáu biểu diễn clip bằng policy V2-C đã khóa; mã hóa H.264 hoặc H.265, giải mã, rồi đo Top-1 bằng hai mạng `r2plus1d_18` và `r3d_18` đóng băng. Kinetics và họ mạng video này được mô tả trong [1, 3]; phiên bản trọng số dùng qua TorchVision xem [4].
- **OD / COCO:** detector phía encoder tạo vùng cần bảo vệ; làm mờ nền ngoài vùng đó trước codec, rồi dùng một detector khác phía decoder để đo COCO mAP. COCO và Faster R-CNN xem [2, 5]. Đây **không** phải V2-C áp dụng sang ảnh.

## Kết quả AR được giữ trong `results/`

**Xác nhận trên holdout 1.000 source video mới: KHÔNG ĐẠT gate đặt trước.** H.264 đạt −19,70% trên `r2plus1d_18` nhưng chỉ −12,52% trên `r3d_18`; H.265 lần lượt là −13,53% và −9,08%. Gate yêu cầu **cả hai** analyzer có point estimate BD-rate Top-1 **< −15%** và BD-accuracy > 0 ở ít nhất một codec. Policy V2-C, tập ID và phép phân tích đã khóa trước khi chấm. [Báo cáo holdout](docs/RESULTS_HOLDOUT_CONFIRM.md), [JSON H.264](results/holdout_confirm/h264_result.json) và [JSON H.265](results/holdout_confirm/h265_result.json) có đủ CI 95%, đường cong, đối chứng và provenance.

| Codec | Analyzer | BD-rate Top-1 trên holdout | CI 95% theo source video |
|---|---|---:|---:|
| H.264 | `r2plus1d_18` | −19,70% | [−22,17%; −17,06%] |
| H.264 | `r3d_18` | −12,52% | [−14,46%; −10,45%] |
| H.264 | `mc3_18` | −2,29% | [−5,23%; +0,69%] |
| H.265 | `r2plus1d_18` | −13,53% | [−15,27%; −11,52%] |
| H.265 | `r3d_18` | −9,08% | [−10,47%; −7,67%] |
| H.265 | `mc3_18` | −1,99% | [−4,35%; +0,21%] |

Holdout này tách **source ID** khỏi các inventory lịch sử đã kiểm toán nhưng vẫn thuộc Kinetics-400; nó chưa kiểm tra chuyển sang dataset khác. Tám so sánh ghép cặp trực tiếp với `area96` và `area112` cố định đều ưu tiên V2-C, nhưng không làm gate chính đạt. `mc3_18` có CI BD-rate chứa 0 ở cả codec. [Kiểm toán tập](docs/HOLDOUT_SPLIT.md) và [preregistration](docs/PREREGISTRATION.md) là các bản đã khóa trước lượt chạy.

Nghiên cứu [V3 chỉ trên DEV](results/v3_dev_policy/README.md) đã preregister một lưới 81 policy ngưỡng rủi ro riêng cho từng analyzer. Không codec nào đạt margin cải thiện calibration đã khóa để thăng cấp policy; V2-C vẫn là fallback, và **holdout V3 CHƯA ĐO**. Lỗi ví dụ tuple V2-C H.265 trong preregistration V3 được [ghi amendment](docs/PREREGISTRATION_V3_AMENDMENT_001.md) sau lượt DEV, không sửa kết quả hay quy tắc chọn.

### Replication trên TEST cũ đã xem

[Gói V2-C 1.000 clip TEST cũ](results/dual_codec_search_v2_confirm_1000/README.md) dùng cùng 1.000 clip được ghép cặp giữa hai codec, năm QP `30,35,40,45,50`, và 2.000 lần bootstrap theo **video nguồn**; BD-rate được tính sau khi gộp hai shard 500 clip, không lấy trung bình BD-rate của shard. Các số sau **không** thuộc holdout mới.

BD-rate ở đây áp dụng phép so sánh đường rate–quality kiểu Bjøntegaard [6] với **Top-1** (hoặc mAP ở pilot OD) làm quality; tài liệu gốc dùng PSNR. Hai codec tương ứng chuẩn ITU-T H.264 và H.265 [7, 8].

| Codec | Analyzer | BD-rate Top-1 | Bootstrap 95% | BD-accuracy (điểm %) |
|---|---|---:|---:|---:|
| H.264 | `r2plus1d_18` | **−22,01%** | [−23,85%, −20,24%] | +10,40 |
| H.264 | `r3d_18` | −14,47% | [−15,69%, −13,21%] | +6,09 |
| H.265 | `r2plus1d_18` | −14,03% | [−15,39%, −12,77%] | +9,92 |
| H.265 | `r3d_18` | −8,72% | [−9,62%, −7,82%] | +5,53 |

**Quyết định trên TEST cũ:** cũng không đạt yêu cầu cả hai analyzer đều có BD-rate Top-1 **< −15%** ở ít nhất một codec. H.264 gần nhất nhưng `r3d_18` còn thiếu 0,53 điểm phần trăm. Cả hai analyzer đều tham gia phát triển policy; TEST này đã được xem trong nghiên cứu V1. Đây là replication trên tập đã biết, tách khỏi kết luận holdout mới ở trên.

Các JSON tổng hợp [H.264](results/dual_codec_search_v2_confirm_1000/h264_result.json) và [H.265](results/dual_codec_search_v2_confirm_1000/h265_result.json) giữ curve, fingerprint và control đồng thời để kiểm toán. Gói kết quả V1 riêng đã được bỏ khỏi nhánh hiện tại; mã và cấu hình V1 cần cho mẫu ghép cặp vẫn được giữ. Những lần Kaggle lỗi không được đưa vào `results/`.

Đã [gộp và kiểm toán analyzer thứ ba `mc3_18`](results/paper_mc3_v2_confirmed/README.md) trên **chính TEST cũ**: BD-rate Top-1 là −3,88% [−6,02%, −1,62%] với H.264 và −2,10% [−3,68%, −0,62%] với H.265, 2.000 bootstrap theo video nguồn. Hai file tái tạo từ bốn shard khớp byte-for-byte với artifact lịch sử; raw record và hash đã được lưu. Kết quả này không thay kết quả `mc3_18` trên holdout mới.

[So sánh với `area96` và `area112` cố định trên DEV](results/paper_downscale_dev/README.md) dùng 200 video ghép cặp mỗi codec. V2-C tốt hơn cả hai downscale thuần ở cả hai analyzer chính trong hai codec, theo BD-rate trực tiếp với CI 95%. Đây là ablation **trên DEV đã dùng trong phát triển**; so sánh xác nhận mới nằm trong [báo cáo holdout](docs/RESULTS_HOLDOUT_CONFIRM.md).

[Chi phí runtime toàn bộ năm QP](docs/RUNTIME_COST.md) đã đo trên 20 clip DEV: overhead trung vị ghép cặp 7,351× (H.264) và 7,066× (H.265), gồm đủ 30 lần encode/decode và suy luận phía encoder mỗi clip. Đây là một giới hạn thực tế của policy hiện tại.

## Kiểm tra ảnh ghép cặp và OD

[Notebook Kinetics cuối cùng](https://www.kaggle.com/code/qktttttttttt/paper-ar-visual-20260924) đã hoàn tất trên CPU: tám clip được chọn bằng hash ID trước khi xem nhãn/kết quả, cùng tám ID cho hai codec, cùng QP 40 và các frame 4/8/12. Panel gồm nguồn, codec-only và stream V2-C; bpp mã hóa lại khớp chính xác cache gốc. Ảnh được phóng bằng nearest-neighbor để hiển thị, không làm đổi pixel mã hóa. **Tám clip chỉ để minh họa**, không thay phép đo Top-1 trên 1.000 clip.

[Notebook COCO val2017](https://www.kaggle.com/code/baoancut/paper-coco-visual-20260924) cũng đã hoàn tất. Đây là pilot OD **100 ảnh** tại 320 px, QP `35,40,45`, `blur4` ngoài vùng bảo vệ so với codec-only. Detector tạo mask là Faster R-CNN MobileNet; detector đánh giá độc lập là Faster R-CNN ResNet50. Tám panel ảnh được chọn bằng ID trong tập đã định, có mask và bản đồ sai khác RGB dùng chung thang 0–64.

| Codec OD | mAP tại QP 40: codec-only → `blur4` | BD-rate theo mAP, ba QP | Bootstrap 95%, 100 lần lấy mẫu ảnh |
|---|---:|---:|---:|
| H.264 | 0,1958 → 0,1886 | **−13,55%** | [−22,20%, −3,00%] |
| H.265 | 0,2126 → 0,1973 | −7,81% | [−16,09%, +2,66%] |

Ở cùng QP, mAP giảm nhẹ; BD-rate âm phản ánh tiết kiệm bit theo toàn đường rate–mAP. H.265 còn bất định vì khoảng bootstrap cắt 0. Pilot 100 ảnh này không phải xác nhận trên toàn COCO val2017 và không chứng minh một phương pháp chung cải thiện cả OD lẫn AR. JSON và record gốc được lưu trong [gói pilot OD](results/od_coco_pilot/README.md) để truy vết các số trên. Provenance của notebook lịch sử chưa đầy đủ, nên gói này **không** được dùng như kết quả xác nhận.

## Mã và tái lập

- [Thiết kế và giới hạn nghiên cứu](docs/PAPER_VALIDATION_PLAN.md), [preregistration đã khóa](docs/PREREGISTRATION.md) và [báo cáo holdout](docs/RESULTS_HOLDOUT_CONFIRM.md): tách nguồn, gate, bootstrap ghép cặp và kết quả xác nhận âm tính.
- [Policy và runner V2](ops/dual_codec_search_confirm_1000.py), [tạo panel Kinetics](ops/paper_ar_visual.py), [OD pilot và panel COCO](ops/probe_background_suppression.py).
- [Runner holdout đã khóa](ops/paper_holdout_confirm.py), [gói record/provenance](ops/package_paper_holdout_confirm.py), [phân tích ablation](ops/paper_validation.py), [runner `mc3_18`](ops/paper_heldout_mc3.py), [runner thời gian chạy](ops/paper_runtime.py) và [baseline downscaling DEV](ops/paper_dev_downscale.py).
- [Cell Kaggle AR](kaggle/paper_ar_visual_cell.sh), [cell Kaggle OD](kaggle/paper_coco_visual_cell.sh) và [công cụ tạo notebook riêng tư](ops/push_paper_visual.py). Cell trong repo này clone `munnn01/pre_updated_v2` tại commit được chỉ định. Hai notebook hoàn tất ở trên được chạy từ bản phát triển `test_pre` với cùng logic đánh giá; không được gọi là lượt chạy lại trên commit repo này.

Kết quả này phù hợp để báo cáo như một **nghiên cứu xác nhận âm tính/replication**: policy tốt hơn downscale cố định trên nguồn Kinetics đã khóa, nhưng trượt gate hai analyzer, lợi ích trên `mc3_18` chưa rõ và overhead encoder cao. Chưa có bằng chứng chuyển miền sang dataset video khác hoặc chứng cứ OD toàn COCO val2017.

## Tài liệu tham khảo

Các nguồn dưới đây là nền tảng cho dữ liệu, mô hình, codec và thước đo; **không phải nguồn của các con số thực nghiệm** trong bảng. Số liệu của repo được lưu trong JSON và notebook liên kết ở trên.

1. Kay, W. và cộng sự (2017). *The Kinetics Human Action Video Dataset*. [arXiv:1705.06950](https://arxiv.org/abs/1705.06950). Bản dữ liệu thực nghiệm: [Kinetics cleaned trên Kaggle](https://www.kaggle.com/datasets/qktttttttttt/kineticscleaned); không đồng nhất bản cleaned này với tập gốc trong bài báo.
2. Lin, T.-Y. và cộng sự (2014). *Microsoft COCO: Common Objects in Context*. [arXiv:1405.0312](https://arxiv.org/abs/1405.0312). Bản dữ liệu thực nghiệm: [COCO 2017 trên Kaggle](https://www.kaggle.com/datasets/awsaf49/coco-2017-dataset).
3. Tran, D. và cộng sự (2018). *A Closer Look at Spatiotemporal Convolutions for Action Recognition*. CVPR, trang 6450–6459. [CVF Open Access](https://openaccess.thecvf.com/content_cvpr_2018/html/Tran_A_Closer_Look_CVPR_2018_paper.html).
4. TorchVision. Tài liệu và trọng số tiền huấn luyện Kinetics-400 cho [`r2plus1d_18`](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.video.r2plus1d_18.html) và [`r3d_18`](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.video.r3d_18.html).
5. Ren, S., He, K., Girshick, R. và Sun, J. (2015). *Faster R-CNN: Towards Real-Time Object Detection with Region Proposal Networks*. NeurIPS 28. [Bài báo](https://papers.nips.cc/paper/2015/hash/14bfa6bb14875e45bba028a21ed38046-Abstract.html); triển khai TorchVision: [MobileNetV3-FPN](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn.html), [ResNet50-FPN](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.detection.fasterrcnn_resnet50_fpn.html).
6. Bjøntegaard, G. (2001). *Calculation of Average PSNR Differences between RD-curves*. ITU-T VCEG-M33. [Bản tài liệu gốc](https://eclass.uoa.gr/modules/document/file.php/D221/%CE%A3%CE%B7%CE%BC%CE%B5%CE%B9%CF%8E%CF%83%CE%B5%CE%B9%CF%82/VCEG-M33%20%28Bjontegaard%20Delta%29.pdf).
7. ITU-T. *Recommendation H.264: Advanced video coding for generic audiovisual services*. [Trang chuẩn](https://www.itu.int/rec/t-rec-h.264).
8. ITU-T. *Recommendation H.265: High efficiency video coding*. [Trang chuẩn](https://www.itu.int/rec/T-REC-H.265).
