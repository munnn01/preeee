# V11 DEV proxy launch

This package records submission of four private CPU notebooks at code/input commit `4ec110533b4b9dee64c93699a6ff60b637c9e7b9`. It is **not a DEV score result**. V11 `mc3_18`, primary DEV scores, bootstrap CI and a fresh holdout remain **CHƯA ĐO**.

- [Launch receipt](launch.json) and its SHA-256 sidecar record notebook URLs, payload hashes, submission outcomes, provenance and planned work.
- [Status snapshot](status_snapshot.json) records the one API check after submission; its statuses are a snapshot, not a live monitor.
- [Verification record](verification.json) pins the pytest log and the worker input/code hashes. The [raw test log](pytest.log) is preserved.
- [DEV input](../../configs/v11_spatial/dev_input.json), SHA-256 `2c48519cb06b7b4580302d629aa7267fe0e35e8fc6ca525d18fa39909114eca5`, contains only 200 source IDs/byte hashes, frozen V2/V6 choices and candidate bpp. No label, correctness or mc3 output enters this input.
- DEV source fingerprint: `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`.

The inherited `provenance.input_sha256` identifies the CAL input used to select the frozen policy. `dev_input_sha256` at the receipt root, and `input_sha256` at the DEV shard-manifest root, identify this separate DEV input. Both are checked independently.

Policy remains `tau=0, slack=0.05, qp_mode=all`, frozen before DEV at `49fb15f6de86f09c6c0a845098cbbf199c405c03`, CAL JSON SHA-256 `280c926a65458a00b192ed1cd0a44e6b341ac6a4f049c96852d5b0e15a410a0e`. The preregistration is commit `00951bd52efeb3c64feb62254cef2aa484431e60`; no threshold, metric or bootstrap change is introduced.

When all four proxy archives are complete and validated, [seal all 200×5 stream choices and commit them](../../docs/V11_DEV_RUNBOOK.md) before publishing four scoring notebooks for all three analyzers. The later merge uses 2,000 paired source-video bootstrap draws, seed `20261008`, and the unchanged DEV go/no-go targets. The original primary gate <−15% remains unchanged and requires a separate source-disjoint confirmatory study for a holdout claim. There is no V11 holdout evaluation in these jobs.
