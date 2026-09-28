%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
REF="__REF__"
STAGE="__STAGE__"
REPO=/kaggle/working/pre_processor
OUT="/kaggle/working/outputs/v7_pixel_proxy/$STAGE"
mkdir -p /kaggle/working/outputs/v7_pixel_proxy
finish() {
  rc=$?
  trap - EXIT
  set +e
  cd /kaggle/working
  tar -czf "v7_pixel_${STAGE}.tgz" outputs/v7_pixel_proxy 2>/dev/null
  echo "[exit] rc=$rc artifact=v7_pixel_${STAGE}.tgz"
  exit "$rc"
}
trap finish EXIT

git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
test "$(git -C "$REPO" rev-parse HEAD)" = "$REF"
cd "$REPO"
ROOT=""
for candidate in /kaggle/input/kineticscleaned /kaggle/input/datasets/qktttttttttt/kineticscleaned; do
  if [ -d "$candidate" ]; then
    ROOT="$candidate"
    break
  fi
done
test -n "$ROOT" || { echo 'Kinetics cleaned source dataset missing' >&2; exit 2; }
python -m ops.v7_pixel_proxy --source-root "$ROOT" --stage "$STAGE" --out-dir "$OUT"
test -s "$OUT/manifest.json"
test -s "$OUT/shard_records.jsonl"
echo "[done] V7 label-free DEV pixel extraction stage=$STAGE"
