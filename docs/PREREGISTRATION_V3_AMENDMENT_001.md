# V3 preregistration amendment 001 — correction of V2-C example tuple

**Recorded 2026-09-27 UTC, after the first V3 calibration/DEV run and before any V3 holdout was selected or evaluated.** This is a disclosure of a factual error in [PREREGISTRATION_V3.md](PREREGISTRATION_V3.md), not a change to the search grid, promotion rule, go/no-go rule, gate or analysis code. The preregistration file remains byte-identical to its lock commit `245dc868f2be32679042dbe1f8a012a43abac47c`.

The preregistration says the 81-policy grid contains V2-C at `(low_r2, low_r3, high_r2, high_r3) = (0.10, 0.10, 0.20, 0.20)`. That tuple is the frozen **H.264** V2-C policy. The frozen **H.265** V2-C policy is `(0.20, 0.20, 0.10, 0.10)`. Both tuples are in the grid fixed before V3 ran. This error was found while inspecting the V3 result after its first run.

The V3 code at commit `c0212e283b0034704bf8154884fdcaed6ef07035` loaded `selected_policy` separately from the original frozen artifact for each codec and used that object as the V2-C comparator and fallback. It did **not** hardcode the mistaken example tuple. No rerun, threshold change, additional candidate or holdout inspection followed this correction. The [V3 DEV report](../results/v3_dev_policy/README.md) discloses the actual comparator and result.
