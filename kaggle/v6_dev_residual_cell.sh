%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
REF="__REF__"
DATASET_OWNER="__DATASET_OWNER__"
DATASET_SLUG="__DATASET_SLUG__"
REPO=/kaggle/working/pre_processor
OUT=/kaggle/working/outputs/v6_dev_residual
mkdir -p "$OUT"
finish() {
  rc=$?
  trap - EXIT
  set +e
  cd /kaggle/working
  tar -czf v6_dev_residual.tgz outputs/v6_dev_residual 2>/dev/null
  echo "[exit] rc=$rc artifact=v6_dev_residual.tgz"
  exit "$rc"
}
trap finish EXIT

git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
test "$(git -C "$REPO" rev-parse HEAD)" = "$REF"
cd "$REPO"
python -m pip install -q 'scikit-learn==1.8.0'
python -c 'import sklearn; print("sklearn", sklearn.__version__); assert sklearn.__version__=="1.8.0"'

INPUT_ROOT="/kaggle/input/$DATASET_SLUG"
if [ ! -f "$INPUT_ROOT/v5_dev_cache_manifest.json" ]; then
  INPUT_ROOT="/kaggle/input/datasets/$DATASET_OWNER/$DATASET_SLUG"
fi
test -f "$INPUT_ROOT/v5_dev_cache_manifest.json" || { echo 'Private locked DEV cache missing' >&2; exit 2; }
export INPUT_ROOT DATASET_OWNER DATASET_SLUG
python - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile

remote = Path(os.environ['INPUT_ROOT'])
locked_path = Path('configs/v5_dev_cache_manifest.json')
assert (remote / 'v5_dev_cache_manifest.json').read_bytes() == locked_path.read_bytes(), 'DEV cache manifest changed'
manifest = json.loads(locked_path.read_text())
assert manifest['dataset_id'] == os.environ['DATASET_OWNER'] + '/' + os.environ['DATASET_SLUG']
assert manifest['archive_sha256'] == 'fba0149d3320398c92ecfd51a194e365b4b04832f8d4334110be19569fc15c17'
archive = remote / manifest['archive_file']
if archive.is_file():
    assert archive.stat().st_size == manifest['archive_bytes']
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    assert digest.hexdigest() == manifest['archive_sha256'], 'DEV cache archive changed'
    cache_root = Path('/kaggle/working/locked_v6_dev')
    cache_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as source:
        for member in source:
            rel = Path(member.name)
            assert member.isfile() and not rel.is_absolute() and '..' not in rel.parts
            assert len(rel.parts) >= 3 and rel.parts[0] == 'dual_codec_search_v2'
            assert rel.parts[1] in ('h264', 'h265')
            destination = cache_root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as src, destination.open('wb') as dst:
                shutil.copyfileobj(src, dst)
    print('[V6 DEV input] compressed archive SHA verified')
else:
    candidates = [remote / 'v5_dev_cache', remote]
    matching = [path for path in candidates
                if all((path / 'dual_codec_search_v2' / codec / 'manifest.json').is_file()
                       for codec in ('h264', 'h265'))]
    assert len(matching) == 1, 'Kaggle DEV cache mount layout changed'
    cache_root = matching[0]
    print('[V6 DEV input] Kaggle-extracted cache found; runner checks every stage hash')
Path('/kaggle/working/v6_cache_root.txt').write_text(str(cache_root))
PY

cp configs/v5_dev_cache_manifest.json "$OUT/input_manifest.json"
CACHE_ROOT="$(cat /kaggle/working/v6_cache_root.txt)"
python -m ops.v6_dev_residual \
  --h264-cache-root "$CACHE_ROOT/dual_codec_search_v2/h264" \
  --h265-cache-root "$CACHE_ROOT/dual_codec_search_v2/h265" \
  --out-dir "$OUT/results" 2>&1 | tee "$OUT/run.log"
test -s "$OUT/results/h264_result.json"
test -s "$OUT/results/h265_result.json"
echo '[done] V6 FIT/CAL/DEV only; no mc3 or holdout outcome'
