# V11 DEV scoring launch

Four private GPU notebooks were submitted at revision `f67391e22c2d9ec2d7be0d34bf307c7c02b5fd77`, after committing all 200×5 stream choices. [Launch receipt](launch.json) and [status snapshot](status_snapshot.json) have SHA-256 sidecars. Notebook URLs and both notebook/metadata payload hashes are in the receipt. Snapshot status is not a live monitor.

[Global selection](../../configs/v11_spatial/dev_selection.json) SHA-256: `e0489ac9e39347bc31ac8c57f3bcc71f9f3d72580f3d5d25be8c1266171cab01`. DEV input SHA-256: `2c48519cb06b7b4580302d629aa7267fe0e35e8fc6ca525d18fa39909114eca5`. Source fingerprint: `6221e93ef728bbd63b9d7b6d9c734297fc028fe608aab34f7783449ac2918258`; individual source hashes are in the committed input and selection. Preregistration commit: `00951bd52efeb3c64feb62254cef2aa484431e60`. Policy CAL freeze: `49fb15f6de86f09c6c0a845098cbbf199c405c03`; policy is unchanged.

Each of four shards evaluates 50 reused DEV sources, H.265 medium and five QPs, all frozen `r2plus1d_18`, `r3d_18`, `mc3_18`, with identity/area112/V2-C/V6/V11 arms. No tuning or new holdout evaluation. Shared streams are scored once; stream hashes and rates are checked against the pre-score global manifest. Timing is evaluation-only.

**Merged DEV BD-rate/BD-accuracy/Top-1 gaps/CI: CHƯA ĐO** until all complete score records are validated. [Runbook](../../docs/V11_DEV_RUNBOOK.md) prescribes 2,000 paired bootstrap draws by source video, seed `20261008`, preserving all QPs, arms and analyzers. These draws are planned for the later merge, not already measured in this launch receipt. Do not change thresholds from the locked preregistration.

[Proxy-only assessment](../../docs/RESULTS_V11_DEV_PROXY.md) precedes scoring and does not establish a transfer improvement. Keep failed or negative outcomes; do not select a new policy from these scores.
