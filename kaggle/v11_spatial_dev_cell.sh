%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
REF="__REF__"
SHARD="__SHARD__"
PHASE="__PHASE__"
REPO=/kaggle/working/pre_processor
OUT="/kaggle/working/outputs/v11_spatial_dev/${PHASE}/shard${SHARD}"
LOG="/kaggle/working/v11_dev_${PHASE}_shard${SHARD}.log"
finish() {
  rc=$?
  trap - EXIT
  set +e
  if [ -d "$OUT" ]; then
    if [ -f "$LOG" ]; then cp "$LOG" "$OUT/run.log"; fi
    cd /kaggle/working
    tar -czf "v11_dev_${PHASE}_shard${SHARD}.tgz" "outputs/v11_spatial_dev/${PHASE}/shard${SHARD}"
  fi
  echo "[exit] rc=$rc phase=$PHASE shard=$SHARD"
  exit "$rc"
}
trap finish EXIT
git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
test "$(git -C "$REPO" rev-parse HEAD)" = "$REF"
cd "$REPO"
python -m ops.v11_spatial_dev preflight --phase "$PHASE"
ROOT=""
for candidate in /kaggle/input/kineticscleaned /kaggle/input/datasets/qktttttttttt/kineticscleaned; do
  if [ -d "$candidate" ]; then ROOT="$candidate"; break; fi
done
test -n "$ROOT" || { echo 'Kinetics source dataset missing' >&2; exit 2; }
python -m ops.v11_spatial_dev "${PHASE}-shard" --source-root "$ROOT" --shard "$SHARD" --out-dir "$OUT" 2>&1 | tee "$LOG"
test -s "$OUT/manifest.json"
test -s "$OUT/shard_records.jsonl"
echo "[done] V11 DEV phase=$PHASE shard=$SHARD"
