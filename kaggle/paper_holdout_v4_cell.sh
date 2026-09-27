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
OUT="/kaggle/working/outputs/paper_holdout_v4/${CODEC}_shard${SHARD}"
mkdir -p "$OUT"
finish() {
  rc=$?
  trap - EXIT
  set +e
  cd /kaggle/working
  tar -czf "paper_holdout_v4_${CODEC}_shard${SHARD}.tgz" \
    "outputs/paper_holdout_v4/${CODEC}_shard${SHARD}" 2>/dev/null
  echo "[exit] rc=$rc codec=$CODEC shard=$SHARD"
  exit "$rc"
}
trap finish EXIT

git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
test "$(git -C "$REPO" rev-parse HEAD)" = "$REF"
cd "$REPO"
python -m pip install -q 'scikit-learn==1.8.0'
python -c 'import sklearn,torch,torchvision,cv2; print("sklearn",sklearn.__version__,"torch",torch.__version__,"torchvision",torchvision.__version__,"cuda",torch.cuda.is_available()); assert sklearn.__version__=="1.8.0" and torch.cuda.is_available()'
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E 'libx264|libx265'

INPUT_ROOT="/kaggle/input/$DATASET_SLUG"
if [ ! -f "$INPUT_ROOT/v4_holdout_manifest.json" ]; then
  INPUT_ROOT="/kaggle/input/datasets/$DATASET_OWNER/$DATASET_SLUG"
fi
test -f "$INPUT_ROOT/v4_holdout_manifest.json" || { echo 'Locked V4 video manifest missing' >&2; exit 2; }
VIDEO_ROOT=/kaggle/working/locked_v4_holdout
export INPUT_ROOT VIDEO_ROOT REF
python - <<'PY'
import hashlib
import json
import os
import zipfile
from pathlib import Path

root = Path(os.environ['INPUT_ROOT'])
target = Path(os.environ['VIDEO_ROOT'])
manifest = json.loads((root / 'v4_holdout_manifest.json').read_text())
sources_path = Path('configs/v4_holdout_source_audit/selected_sources.json')
sources = json.loads(sources_path.read_text())
index_path = Path('configs/v4_holdout_source_audit/index.json')
index = json.loads(index_path.read_text())
freeze_path = Path('configs/v4_frozen/manifest.json')
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
assert manifest['freeze_manifest_sha256'] == sha(freeze_path)
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
    candidates = [root, root / 'videos']
    matching = [candidate for candidate in candidates
                if (candidate / expected[0]).is_file()]
    assert len(matching) == 1, 'Kaggle V4 video mount layout changed'
    video_root = matching[0]
actual = sorted(path.name for path in (video_root / 'videos').glob('*.mp4'))
assert actual == sorted(row['filename'] for row in sources['selected'])
Path('/kaggle/working/locked_v4_video_root.txt').write_text(str(video_root))
print('[V4 holdout-input] manifest and 1000 video names verified; runner checks every video SHA')
PY
VIDEO_ROOT="$(cat /kaggle/working/locked_v4_video_root.txt)"
test -d "$VIDEO_ROOT/videos"

python -m ops.paper_holdout_v4 primary \
  --index configs/v4_holdout_source_audit/index.json \
  --video-root "$VIDEO_ROOT" --prereg-commit "$REF" \
  --codec "$CODEC" --shard "$SHARD" \
  --out-dir "$OUT/primary" 2>&1 | tee "$OUT/primary.log"
test -s "$OUT/primary/shard_records.jsonl"

python -m ops.paper_holdout_v4 mc3 \
  --index configs/v4_holdout_source_audit/index.json \
  --video-root "$VIDEO_ROOT" --prereg-commit "$REF" \
  --codec "$CODEC" --shard "$SHARD" \
  --primary-dir "$OUT/primary" --out-dir "$OUT/mc3" \
  2>&1 | tee "$OUT/mc3.log"
test -s "$OUT/mc3/shard_records.jsonl"
echo '[done] one locked V4 holdout codec/shard, primary plus mc3'
