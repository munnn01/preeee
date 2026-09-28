%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
REF="__REF__"
START="__START__"
STOP="__STOP__"
REPO=/kaggle/working/pre_processor
OUT=/kaggle/working/v6_archive_shard

git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
test "$(git -C "$REPO" rev-parse HEAD)" = "$REF"
cd "$REPO"
python -m ops.v6_holdout_archive_shard --start "$START" --stop "$STOP" --out-dir "$OUT"
test -s "$OUT/shard_manifest.json"
cd /kaggle/working
tar -cf "v6_archive_${START}_${STOP}.tar" -C "$OUT" parts videos shard_manifest.json
sha256sum "v6_archive_${START}_${STOP}.tar"
echo "[done] V6 byte-only preflight archives $START..$STOP"
