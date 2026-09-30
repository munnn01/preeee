# pre_processor — nén hướng nhiệm vụ cho Action Recognition và Object Detection

Repo này nghiên cứu can thiệp miền pixel **trước codec chuẩn** để giảm bitrate mà vẫn giữ hiệu năng tác vụ. Hai đường đánh giá độc lập:

- **AR / Kinetics:** chọn một trong sáu biểu diễn clip bằng policy đã khóa; mã hóa H.264 hoặc H.265, giải mã, rồi đo Top-1 bằng hai mạng `r2plus1d_18` và `r3d_18` đóng băng, cùng `mc3_18` độc lập. Kinetics và họ mạng video này được mô tả trong [1, 3]; phiên bản trọng số dùng qua TorchVision xem [4].
- **OD / COCO:** detector phía encoder tạo vùng cần bảo vệ; làm mờ nền ngoài vùng đó trước codec, rồi dùng một detector khác phía decoder để đo COCO mAP. COCO và Faster R-CNN xem [2, 5]. Đây **không** phải V2-C áp dụng sang ảnh.

## Kết quả AR được giữ trong `results/`

[V10 spatial gate](docs/V10_SPATIAL_GATE_DESIGN.md) đã có [dự thảo preregistration](docs/PREREGISTRATION_V10_SPATIAL_GATE.md), [source plan](configs/v10_spatial_plan.json), mã chọn stream theo QP và [runbook bốn shard](docs/V10_SPATIAL_GATE_RUNBOOK.md). Proxy gradient/Laplacian chỉ đọc pixel đã giải mã; CAL chọn tham số bằng hai analyzer chính, rồi freeze trước khi chấm DEV với mc3. **V10 CAL/DEV/holdout: CHƯA ĐO**; giao thức hiện còn draft. Kiểm toán CAL cũ phục vụ thiết kế không phải kết quả V10.

[V9 H.265 chroma-only trên 100 nguồn CAL cũ](docs/RESULTS_V9_CHROMA_CAL.md) **KHÔNG QUA** quy tắc phát triển đã khóa: BD-rate trực tiếp V9 so với V6 trên `mc3_18` là +2,56% (CI 95% [−3,60%; +8,85%]); hai analyzer chính của V9 so với identity chỉ đạt −1,90% và −5,77%, không đạt mục tiêu < −10%. Chỉnh chroma làm mất lợi ích V6 trên cả hai analyzer chính. Đây là tập CAL đã được dùng trong phát triển và `mc3_18` đã từng được xem; **V9 DEV và holdout mới CHƯA ĐO**. [JSON, archive và hash](results/v9_chroma_cal/README.md).

[V7 H.265 trên CAL/DEV cũ](docs/RESULTS_V7_DEV.md) đã chọn một proxy pixel trước codec với lưới và điều kiện được [khóa trước](docs/PREREGISTRATION_V7_TRANSFER.md). Trên 200 nguồn DEV từng dùng để phát triển, BD-rate Top-1 so với identity là **−16,21%** (`r2plus1d_18`) và **−11,21%** (`r3d_18`): hai point estimate qua mục tiêu kỹ thuật < −10%, nhưng `r3d_18` chưa qua gate nghiên cứu gốc < −15%. [Chẩn đoán `mc3_18` sau khi freeze V7](docs/RESULTS_V7_MC3_DEV.md) trên cùng DEV cho **+1,70%** BD-rate trực tiếp V7 so với V6 (CI 95% [−0,77%; +4,33%]); **không có bằng chứng cải thiện analyzer thứ ba**. **V7 holdout nguồn mới: CHƯA ĐO.** [JSON và provenance hai analyzer chính](results/v7_dev_transfer/README.md), [JSON và raw record `mc3_18`](results/v7_mc3_dev/README.md).

**V6 H.265 trên 1.000 nguồn Kinetics-400 mới: KHÔNG ĐẠT gate đặt trước.** BD-rate Top-1 so với identity là −13,62% (`r2plus1d_18`) và −11,11% (`r3d_18`), chưa đạt ngưỡng nghiêm ngặt < −15% ở cả hai analyzer. Trực tiếp so với V2-C trên cùng nguồn, V6 cải thiện −0,85% và −2,36% ở hai analyzer này, nhưng trên `mc3_18` là **+1,53%** (CI 95% [−0,49%; +3,32%]): không có bằng chứng cải thiện analyzer thứ ba. V6 H.264 **CHƯA ĐO**. Đây là xác nhận trên source-ID mới trong K400, không phải chuyển miền; `mc3_18` đã được xem trong nghiên cứu trước. [Báo cáo V6 holdout](docs/RESULTS_HOLDOUT_V6.md), [JSON](results/paper_holdout_v6/h265_result.json), [raw record và provenance](results/paper_holdout_v6/README.md).

**V4 trên holdout source-disjoint mới gồm 1.000 video: ĐẠT gate đặt trước qua H.264, nhưng chưa chứng minh chuyển giao sang `mc3_18`.** Cả hai analyzer chính phải có BD-rate Top-1 < −15% và BD-accuracy > 0 ở ít nhất một codec. H.264 đạt −22,11% (`r2plus1d_18`) và −23,63% (`r3d_18`); H.265 không đạt gate riêng codec. `mc3_18` có BD-rate +1,92% ở H.264 và −0,50% ở H.265, cả hai CI 95% chứa 0; Top-1 thấp hơn identity tại cả năm QP ở cả hai codec. V4 đã khóa trước khi chấm; `mc3_18` không tham gia fit/chọn policy. [Báo cáo V4](docs/RESULTS_HOLDOUT_V4.md), [gói record và provenance](results/paper_holdout_v4/README.md), [JSON H.264](results/paper_holdout_v4/h264_result.json) và [JSON H.265](results/paper_holdout_v4/h265_result.json) cho đủ số và CI. Tập vẫn thuộc Kinetics-400, chưa phải chuyển miền. Runtime toàn bộ selector V4: **CHƯA ĐO**.

### V2-C trên holdout trước đó

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

[Oracle chẩn đoán trên DEV](results/v4_dev_oracle/README.md) dùng nhãn thật để chọn candidate không làm mất dự đoán đúng: BD-rate tham khảo đạt −27,39%/−26,54% ở H.264 và −18,12%/−15,68% ở H.265 trên hai analyzer. Đây **không phải policy triển khai được hoặc kết quả holdout**; nó chỉ cho thấy bộ sáu candidate có dư địa để nghiên cứu một selector không đọc nhãn.

[Policy V4 trên FIT/CALIBRATION/DEV](results/v4_dev_policy/README.md) dùng hai mô hình xác suất đúng với 41 feature không nhãn cho mỗi codec. Cả hai codec được thăng cấp theo CALIBRATION; H.265 qua quy tắc go/no-go trên DEV, còn H.264 trượt guard same-QP của `r3d_18` trên DEV (−2,00 điểm % so với ngưỡng ≥−1,00). Theo [giao thức V4](docs/PREREGISTRATION_V4.md), điều kiện mở holdout là có **ít nhất một codec** qua go/no-go; holdout mới đã được chạy và báo đầy đủ cả hai codec ở trên. Không dùng holdout V2 để fit/chọn V4.

[V5 đã preregister](docs/PREREGISTRATION_V5.md) một phép thử **chỉ trên CAL/DEV**: giữ nguyên mô hình V4, yêu cầu hai analyzer chính đồng ý với identity về lớp dự đoán trước khi chọn stream, và ràng buộc BD-rate mỗi analyzer không kém V2-C quá 1,00 điểm phần trăm trên CAL. Notebook sửa layout đã chạy xong: **0/81 policy V5 thỏa điều kiện trên CAL ở cả H.264 và H.265**, nên dừng trước DEV đúng giao thức; không có policy V5 được chọn. **V5 DEV, `mc3_18` và holdout mới: CHƯA ĐO.** Đây là nghiên cứu phát triển sau khi đã xem kết quả V4; không dùng `mc3_18` hoặc holdout đã xem để chọn ngưỡng. [Báo cáo V5](docs/RESULTS_V5_DEV.md), [JSON và hash gốc từ Kaggle](results/v5_dev_agreement/README.md), [amendment kỹ thuật](docs/V5_DEV_TECHNICAL_AMENDMENT.md).

[V6 đã preregister](docs/PREREGISTRATION_V6.md) một selector bắt đầu từ V2-C, học trên FIT xác suất một candidate làm mất hoặc lấy lại dự đoán đúng của từng analyzer chính, rồi chọn trong lưới cố định trên CAL với ràng buộc BD-rate gần V2-C và một proxy khoảng cách đặc trưng tới nguồn. Lượt Kaggle FIT/CAL/DEV đã hoàn tất: **H.265 qua go/no-go phát triển**, có BD-rate trực tiếp V6 so với V2-C trên DEV là −1,75% (`r2plus1d_18`) và −2,19% (`r3d_18`); **H.264 trượt** điều kiện DEV. [Báo cáo V6 DEV](docs/RESULTS_V6_DEV.md) và [JSON, mô hình, hash gốc](results/v6_dev_residual/README.md) ghi đầy đủ CI và điều kiện. Lượt xác nhận H.265 trên source mới ở đầu mục này cho thấy proxy chưa tạo được lợi ích chuyển giao xác nhận trên `mc3_18`.

[Giao thức xác nhận V6 H.265](docs/PREREGISTRATION_V6_HOLDOUT.md) và [kiểm toán nguồn V6](docs/HOLDOUT_SPLIT_V6.md) đã khóa policy/model, 2.000 ID ứng viên và **1.000 video nguồn mới** với SHA-256 từng video; nguồn này không trùng ID holdout V2/V4 hay DEV. Index nhãn được tạo sau commit khóa video. Hai shard đã chạy và gộp theo giao thức; [báo cáo kết quả](docs/RESULTS_HOLDOUT_V6.md) nêu rõ gate H.265 **KHÔNG ĐẠT** và chưa có bằng chứng `mc3_18` cải thiện so với V2-C. `mc3_18` đã được xem trong các nghiên cứu trước, vì vậy dù có holdout nguồn mới cũng không thể gọi nó là kiến trúc chưa từng quan sát.

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

[Chi phí runtime toàn bộ năm QP](docs/RUNTIME_COST.md) đã đo **V2-C** trên 20 clip DEV: overhead trung vị ghép cặp 7,351× (H.264) và 7,066× (H.265), gồm đủ 30 lần encode/decode và suy luận phía encoder mỗi clip. Đây là một giới hạn thực tế của V2-C. **Runtime đầy đủ của V4: CHƯA ĐO**; không lấy tỉ lệ V2-C làm số đo V4.

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
- [Preregistration V4](docs/PREREGISTRATION_V4.md), [kiểm toán split V4](docs/HOLDOUT_SPLIT_V4.md) và [báo cáo V4](docs/RESULTS_HOLDOUT_V4.md): policy, nguồn, gate và kết quả mới; [amendment kỹ thuật](docs/V4_HOLDOUT_TECHNICAL_AMENDMENT.md) ghi sự cố hash CRLF/LF trước lượt chạy hoàn tất.
- [Policy và runner V2](ops/dual_codec_search_confirm_1000.py), [tạo panel Kinetics](ops/paper_ar_visual.py), [OD pilot và panel COCO](ops/probe_background_suppression.py).
- [Runner và merge V4](ops/paper_holdout_v4.py), [gói V4](results/paper_holdout_v4/README.md).
- [Runner holdout đã khóa](ops/paper_holdout_confirm.py), [gói record/provenance](ops/package_paper_holdout_confirm.py), [phân tích ablation](ops/paper_validation.py), [runner `mc3_18`](ops/paper_heldout_mc3.py), [runner thời gian chạy](ops/paper_runtime.py) và [baseline downscaling DEV](ops/paper_dev_downscale.py).
- [Cell Kaggle AR](kaggle/paper_ar_visual_cell.sh), [cell Kaggle OD](kaggle/paper_coco_visual_cell.sh) và [công cụ tạo notebook riêng tư](ops/push_paper_visual.py). Cell trong repo này clone `munnn01/pre_updated_v2` tại commit được chỉ định. Hai notebook hoàn tất ở trên được chạy từ bản phát triển `test_pre` với cùng logic đánh giá; không được gọi là lượt chạy lại trên commit repo này.

V2-C là **nghiên cứu xác nhận âm tính/replication** trên gate hai analyzer; V4 là **xác nhận dương tính cho gate đó trên holdout source-disjoint mới**. V6 H.265 là **xác nhận âm tính cho chính policy V6 theo gate**; cải thiện nhỏ trên hai analyzer chính so với V2-C không đi kèm bằng chứng cải thiện `mc3_18`. Chưa có số runtime đầy đủ của selector V4/V6 hoặc bằng chứng chuyển miền sang dataset video khác. OD chưa được xác nhận trên toàn COCO val2017.

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
