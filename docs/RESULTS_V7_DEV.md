# V7 H.265: kết quả phát triển trên CAL/DEV cũ

[Giao thức V7](PREREGISTRATION_V7_TRANSFER.md) được commit tại `6c4a03d4e95d3f549adddf0a890704a334eb3a39` trước mã và phép đo. Worker/runner chạy ở commit `2c0a29836101fced7a91b7ff136a8b929b6d7c2b`, trên 200 video CAL và 200 video DEV đã thuộc pilot V2. Đây là **nghiên cứu phát triển**, không phải holdout độc lập. `mc3_18` không được chạy hoặc dùng để chọn V7; hiệu quả chuyển giao của V7 sang `mc3_18` **CHƯA ĐO**.

Hai notebook private [CAL](https://www.kaggle.com/code/shungg05/v7-h265-pixel-cal-2c0a298) và [DEV](https://www.kaggle.com/code/dieulinhh/v7-h265-pixel-dev-2c0a298) chỉ đọc video nguồn để trích proxy pixel không nhãn. Mỗi archive có đúng 200 record; hash record khớp manifest. Runner ghép chúng với cache V2 H.265 và bốn model event V6 đã đóng băng, chọn policy **chỉ trên CAL** rồi mới đọc correctness DEV. [h265_result.json](../results/v7_dev_transfer/h265_result.json) có SHA-256 `7026c427f92574508db966d61e082018e0c18a66c50592d24d9c2fe9046c742c`; hai lần chạy từ cùng input cho file trùng hash từng byte. [Gói record và provenance](../results/v7_dev_transfer/README.md) lưu đủ manifest, SHA và commit.

## CAL và quyết định đã khóa

Lưới cố định gồm 8 policy. Hai policy qua tất cả điều kiện CAL. Policy được chọn theo mean pixel proxy nhỏ nhất trong số hợp lệ: `threshold=-0.02`, `pixel_weight=0.25`. Mean proxy của V6 là `0.377817`, của V7 là `0.268471`; BD-rate Top-1 V7 so với identity trên CAL là **−14,33%** (`r2plus1d_18`) và **−14,89%** (`r3d_18`). Tám hàng, thứ tự chọn, BD-accuracy, same-QP gap và choice counts nằm trong JSON; không đổi lưới hoặc ngưỡng sau khi xem CAL.

## Một lượt DEV với policy đã chọn

| Analyzer | V6 so với identity: BD-rate Top-1, CI 95% | V7 so với identity: BD-rate Top-1, CI 95% | V7 so với V6 trực tiếp: BD-rate, CI 95% | BD-accuracy V7 (điểm %) |
|---|---:|---:|---:|---:|
| `r2plus1d_18` | −16,26% [−19,38%; −12,72%] | **−16,21%** [−19,40%; −12,59%] | +0,05% [−0,58%; +0,77%] | +11,82 |
| `r3d_18` | −10,69% [−13,33%; −8,04%] | **−11,21%** [−13,91%; −8,42%] | −0,60% [−1,63%; +0,33%] | +6,69 |

**DEV go/no-go của V7 ĐẠT theo tiêu chí phát triển đã đặt:** cả hai point BD-rate <−10%, BD-accuracy dương, worst same-QP gap lần lượt +0,50 và 0,00 điểm %, BD-rate mỗi analyzer không kém V6 quá 1,00 điểm phần trăm, và mean proxy giảm. Tuy nhiên, CI của `r3d_18` vươn lên trên −10% và CI của hai so sánh trực tiếp V7–V6 đều chứa 0. Vì vậy chưa có bằng chứng V7 cải thiện BD-rate của hai analyzer chính so với V6. Gate gốc **<−15% trên cả hai analyzer** vẫn không đạt trên DEV vì `r3d_18` là −11,21%; ngưỡng này không được thay bằng mục tiêu kỹ thuật −10%.

Mean proxy pixel DEV giảm từ `0.373779` (V6) xuống `0.269091` (V7), hiệu ghép cặp `−0.104687`, CI 95% `[−0.122163; −0.086832]`. Đây là tín hiệu trước codec, **không phải độ chính xác của `mc3_18`**. V7 chọn `identity128` ở 472/1.000 cặp nguồn–QP, `area112` ở 94 và `area96` ở 245; V6 lần lượt là 299, 448 và 136. Thay đổi tỷ lệ lựa chọn chỉ là mô tả, chưa xác định tác động lên `mc3_18`.

Mỗi CI dùng 2.000 bootstrap percentile ghép cặp theo **source video**, seed `20261003`; đường cong gộp trên 200 nguồn trước khi tính BD-rate. Source fingerprint CAL `ce5acf9334d4f683fdc7757d53b0d5be0ce80cc5a6fd4a4340e30c9357e79721`, DEV `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`; plan SHA-256 `5b0a32d1d0a1759b50232f0c297ee35ee5cfe0cfdf00c53b587781baa5afebc2`. Mỗi video trích proxy có SHA-256 byte trong record và JSON. Pilot V2 không lưu SHA của video gốc, nên không thể chứng minh hồi cứu rằng byte video khi trích proxy hoàn toàn giống byte từng dùng để tạo cache V2; ID và cấu hình lấy mẫu đã được đối chiếu. Runtime toàn bộ V7 **CHƯA ĐO**.

Hai notebook đầu tiên ở commit `f75ae09547b56c0457d195c097392542fd0d6b2c` lỗi ở bước so sánh CRLF/LF của plan **trước khi tạo record**. [Amendment kỹ thuật](V7_DEV_TECHNICAL_AMENDMENT_001.md) ghi log, nguyên nhân và sửa kiểm tra byte; không đổi giao thức. Tập CAL/DEV đã được xem qua nhiều phiên bản, và `mc3_18` từng được xem ở các nghiên cứu trước. Kết quả V7 chỉ biện minh cho một phép xác nhận tương lai trên nguồn mới sau khi freeze policy; không được dùng holdout V6 để chỉnh V7.
