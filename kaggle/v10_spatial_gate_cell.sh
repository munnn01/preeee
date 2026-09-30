%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
REF="__REF__"
PREREG="__PREREG__"
STAGE="__STAGE__"
SHARD="__SHARD__"
REPO=/kaggle/working/pre_processor
OUT="/kaggle/working/outputs/v10_spatial_gate/${STAGE}/shard${SHARD}"
LOG="/kaggle/working/v10_${STAGE}_shard${SHARD}.log"
finish() {
  rc=$?
  trap - EXIT
  set +e
  if [ -d "$OUT" ]; then
    cp "$LOG" "$OUT/run.log"
    cd /kaggle/working
    tar -czf "v10_${STAGE}_shard${SHARD}.tgz" "outputs/v10_spatial_gate/${STAGE}/shard${SHARD}"
  fi
  echo "[exit] rc=$rc stage=$STAGE shard=$SHARD"
  exit "$rc"
}
trap finish EXIT
git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
test "$(git -C "$REPO" rev-parse HEAD)" = "$REF"
cd "$REPO"
python -m ops.v10_spatial_gate --prereg-commit "$PREREG" preflight
ROOT=""
for candidate in /kaggle/input/kineticscleaned /kaggle/input/datasets/qktttttttttt/kineticscleaned; do
  if [ -d "$candidate" ]; then ROOT="$candidate"; break; fi
done
test -n "$ROOT" || { echo 'Kinetics source dataset missing' >&2; exit 2; }
python -m ops.v10_spatial_gate --prereg-commit "$PREREG" shard --stage "$STAGE" --source-root "$ROOT" --shard "$SHARD" --out-dir "$OUT" 2>&1 | tee "$LOG"
test -s "$OUT/manifest.json"
test -s "$OUT/shard_records.jsonl"
test -s "$OUT/proxy_records.jsonl"
echo "[done] V10 stage=$STAGE shard=$SHARD"
