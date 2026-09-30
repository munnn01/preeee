# V9 H.265 chroma-only CAL artifact inventory

The [merged result](h265_result.json) contains source IDs and source-video SHA-256, full five-QP curves, three-analyzer direct comparisons, 2,000 paired source-video bootstrap resamples, seed `20261006`, fingerprint and commit hashes. `h265_result.sha256` verifies its exact bytes. The four original Kaggle archives hold per-source measurements, source hashes, manifests and run logs; they contain no source video or credential. The source fingerprint is `3c31de5d56807dbbe2560a8b98c2bc43c2f46e3294cf2dd4248d5449b5a60992`.

| Shard | Kaggle account and notebook | Archive SHA-256 |
|---:|---|---|
| 0 | [shungg05](https://www.kaggle.com/code/shungg05/v9-chroma-cal-s0-f7872f2) | `a40f71dad9ed33fe38dab1fe9fc61a272bab5b80f1811703144b15d4d3efb7cb` |
| 1 | [dieulinhh](https://www.kaggle.com/code/dieulinhh/v9-chroma-cal-s1-f7872f2) | `f3dcf3c0313a799be70af0adccd29b33f72cdd82b996c516879c33aa8fe39f27` |
| 2 | [huolgggnuyen](https://www.kaggle.com/code/huolgggnuyen/v9-chroma-cal-s2-f7872f2) | `fed4248345f94935a52b4f411cd8c95ee2d452da85a3174bcb5b63840bb62bbe` |
| 3 | [baooo25r](https://www.kaggle.com/code/baooo25r/v9-chroma-cal-s3-f7872f2) | `c59e605854acbf74ea9b578fc13f9f81bf53b6de11d06c47963c5f1342264ba8` |

All shards used code commit `f7872f249e48e2d8f793f3315323f81cec7baf25`, preregistration commit `56485c739e257de74b1e40d658ec77302973fd03`, frozen selection SHA-256 `625abf5e964dfe969ea491e1aae530689bab2031757075542166905d21d05f24`, and 25 distinct source videos. This is reused CAL development evidence. See the [interpretation](../../docs/RESULTS_V9_CHROMA_CAL.md) and [locked protocol](../../docs/PREREGISTRATION_V9_CHROMA_CAL.md). No V9 DEV or holdout result is present.
