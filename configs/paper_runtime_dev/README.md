# Fixed 20-clip DEV sample for the full runtime benchmark

The 20 `sample_ids.json` entries are the class-balanced, hash-selected DEV clips in the earlier QP-40 runtime pilot manifest (historical execution commit `b25f75d767f24163a1edc6f976c52c7051981057`; source manifest SHA-256 `6586b9596190e6cdfe1c1e66ed19a10f554dab248d26dd4b36eaf428c52f2895`). They were fixed before the five-QP runtime measurements. The old source index SHA-256 is `1a7adb6ad3aac2fa3fc93767c9567e49441b35f7ad6375fe7e1949ef0507acb2`.

| File | SHA-256 | Contents |
|---|---|---|
| `index.json` | `1c04cbc454441ca8b102d11efecd31bf932f6be10cf958319370b9c4650a3bce` | 20 DEV labels and absolute local video paths |
| `sample_ids.json` | `3e6e1dd4570b702bb3e0dddc9d25e9afb1c1faa043b6dab9099e7f53f58f740e` | fixed sample order, shared by both codecs |
| `source_files.json` | `36e11ee65108b834c4b2878c06c5b435773e29f02c62c2e8e41f39c01cd71551` | Kaggle relative file path, byte length and SHA-256 for each video |

The absolute paths point into the local audit workspace and can be remapped on another machine after verifying the video hashes. These 20 videos are from `qktttttttttt/kineticscleaned` DEV; they are **not** the new holdout. QP-40 results are not substituted for the full five-QP benchmark.
