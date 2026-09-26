# COCO val2017 exploratory pilot, 100 images

This package preserves the original [Kaggle pilot](https://www.kaggle.com/code/baoancut/paper-coco-visual-20260924) aggregate JSON and paired per-image NPZ without recomputing or modifying either file. `probe_bgsuppress.json` contains the codec curves, QP-40 mAP values, BD-rate and 100 paired-image bootstrap draws cited in the project README. `per_image_records.npz` contains the underlying per-image records. The intervention is background `blur4` guided by an object detector, **not** the frozen V2-C action-recognition policy.

| File | SHA-256 |
|---|---|
| `probe_bgsuppress.json` | `438e47b31ee5ea6fdb58473075f30cd21c4a49f3e636eb65802a71974051fa41` |
| `per_image_records.npz` | `58e5864c7da7d9e6ee75746b7cc6b9425dac6336b055640852866b4d7b355b4e` |

Source extraction: `paper_visual_coco_complete/extracted/outputs/paper_coco_visual/` in the local audit archive; packaging parent commit `8fae9ec`. The historical notebook's exact execution commit and original dataset index SHA are **CHƯA XÁC MINH** in the available output, so this package is not treated as confirmatory evidence. No full COCO val2017 evaluation has been run.
