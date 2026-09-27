%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
REF="__REF__"
CODEC="__CODEC__"
SHARD="__SHARD__"
DATASET_OWNER="__DATASET_OWNER__"
DATASET_SLUG="__DATASET_SLUG__"
REPO=/kaggle/working/pre_processor
OUT="/kaggle/working/outputs/paper_holdout_confirm/${CODEC}_shard${SHARD}"
mkdir -p "$OUT"
finish() {
  rc=$?
  trap - EXIT
  set +e
  cd /kaggle/working
  tar -czf "paper_holdout_${CODEC}_shard${SHARD}.tgz" \
    "outputs/paper_holdout_confirm/${CODEC}_shard${SHARD}" 2>/dev/null
  echo "[exit] rc=$rc codec=$CODEC shard=$SHARD"
  exit "$rc"
}
trap finish EXIT

git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
test "$(git -C "$REPO" rev-parse HEAD)" = "$REF"
cd "$REPO"
python -c 'import torch, torchvision, cv2; print("torch",torch.__version__,"torchvision",torchvision.__version__,"cuda",torch.cuda.is_available()); assert torch.cuda.is_available(), "GPU required"'
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E 'libx264|libx265'

VIDEO_ROOT="/kaggle/input/$DATASET_SLUG"
if [ ! -d "$VIDEO_ROOT/videos" ]; then
  VIDEO_ROOT="/kaggle/input/datasets/$DATASET_OWNER/$DATASET_SLUG"
fi
test -d "$VIDEO_ROOT/videos" || { echo 'Locked video dataset missing' >&2; exit 2; }

python -m ops.paper_holdout_confirm primary \
  --index configs/holdout_source_audit/index.json \
  --video-root "$VIDEO_ROOT" --prereg-commit "$REF" \
  --codec "$CODEC" --shard "$SHARD" \
  --out-dir "$OUT/primary" 2>&1 | tee "$OUT/primary.log"
test -s "$OUT/primary/shard_records.jsonl"

python -m ops.paper_holdout_confirm mc3 \
  --index configs/holdout_source_audit/index.json \
  --video-root "$VIDEO_ROOT" --prereg-commit "$REF" \
  --codec "$CODEC" --shard "$SHARD" \
  --primary-dir "$OUT/primary" --out-dir "$OUT/mc3" \
  2>&1 | tee "$OUT/mc3.log"
test -s "$OUT/mc3/shard_records.jsonl"
echo '[done] one locked holdout codec/shard, primary plus mc3'
