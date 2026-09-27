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

INPUT_ROOT="/kaggle/input/$DATASET_SLUG"
if [ ! -f "$INPUT_ROOT/holdout_manifest.json" ]; then
  INPUT_ROOT="/kaggle/input/datasets/$DATASET_OWNER/$DATASET_SLUG"
fi
test -f "$INPUT_ROOT/holdout_manifest.json" || { echo 'Locked video manifest missing' >&2; exit 2; }
VIDEO_ROOT=/kaggle/working/locked_holdout
export INPUT_ROOT VIDEO_ROOT REF
python - <<'PY'
import hashlib
import json
import os
import zipfile
from pathlib import Path

root = Path(os.environ['INPUT_ROOT'])
target = Path(os.environ['VIDEO_ROOT'])
manifest = json.loads((root / 'holdout_manifest.json').read_text())
sources_path = Path('configs/holdout_source_audit/selected_sources.json')
sources = json.loads(sources_path.read_text())
index_path = Path('configs/holdout_source_audit/index.json')
index = json.loads(index_path.read_text())
def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()
assert manifest['preregistration_commit'] == os.environ['REF']
assert manifest['id_lock_commit'] == index['meta']['locked_commit']
assert manifest['index_sha256'] == sha(index_path)
assert manifest['selected_sources_sha256'] == sha(sources_path)
assert manifest['source_fingerprint'] == sources['selected_source_fingerprint']
assert manifest['source_count'] == len(sources['selected']) == 1000
expected = ['videos/' + row['filename'] for row in sources['selected']]
if (root / 'videos.zip').is_file():
    assert sha(root / 'videos.zip') == manifest['zip_sha256']
    with zipfile.ZipFile(root / 'videos.zip') as archive:
        assert archive.namelist() == expected
        archive.extractall(target)
    video_root = target
else:
    # Kaggle expands uploaded ZIPs under a directory named after the ZIP.
    candidates = [root, root / 'videos']
    matching = [candidate for candidate in candidates
                if (candidate / expected[0]).is_file()]
    assert len(matching) == 1, 'Kaggle video mount layout changed'
    video_root = matching[0]
actual = sorted(path.name for path in (video_root / 'videos').glob('*.mp4'))
assert actual == sorted(row['filename'] for row in sources['selected'])
Path('/kaggle/working/locked_video_root.txt').write_text(str(video_root))
print('[holdout-input] manifest and 1000 video names verified; runner will check every video SHA')
PY
VIDEO_ROOT="$(cat /kaggle/working/locked_video_root.txt)"
test -d "$VIDEO_ROOT/videos"

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
