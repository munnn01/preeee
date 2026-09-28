%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
REF="__REF__"
SHARD="__SHARD__"
REPO=/kaggle/working/pre_processor
OUT="/kaggle/working/outputs/v8_motion_pilot/shard${SHARD}"
mkdir -p "$OUT"
finish() {
  rc=$?
  trap - EXIT
  set +e
  cd /kaggle/working
  tar -czf "v8_motion_pilot_shard${SHARD}.tgz" "outputs/v8_motion_pilot/shard${SHARD}" 2>/dev/null
  echo "[exit] rc=$rc shard=$SHARD artifact=v8_motion_pilot_shard${SHARD}.tgz"
  exit "$rc"
}
trap finish EXIT

git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
test "$(git -C "$REPO" rev-parse HEAD)" = "$REF"
cd "$REPO"
python -c 'import torch,torchvision,cv2; print("torch",torch.__version__,"torchvision",torchvision.__version__,"opencv",cv2.__version__,"cuda",torch.cuda.is_available())'
ffmpeg -hide_banner -encoders 2>/dev/null | grep libx265
ROOT=""
for candidate in /kaggle/input/kineticscleaned /kaggle/input/datasets/qktttttttttt/kineticscleaned; do
  if [ -d "$candidate" ]; then
    ROOT="$candidate"
    break
  fi
done
test -n "$ROOT" || { echo 'Kinetics cleaned source dataset missing' >&2; exit 2; }
python -m ops.v8_motion_pilot shard --source-root "$ROOT" --shard "$SHARD" --out-dir "$OUT" 2>&1 | tee "$OUT/run.log"
test -s "$OUT/manifest.json"
test -s "$OUT/shard_records.jsonl"
echo "[done] V8 CAL motion-protected pilot shard=$SHARD"

