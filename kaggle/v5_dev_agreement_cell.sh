%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
REF="__REF__"
DATASET_OWNER="__DATASET_OWNER__"
DATASET_SLUG="__DATASET_SLUG__"
REPO=/kaggle/working/pre_processor
OUT=/kaggle/working/outputs/v5_dev_agreement
mkdir -p "$OUT"
finish() {
  rc=$?
  trap - EXIT
  set +e
  cd /kaggle/working
  tar -czf v5_dev_agreement.tgz outputs/v5_dev_agreement 2>/dev/null
  echo "[exit] rc=$rc artifact=v5_dev_agreement.tgz"
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
test -f "$INPUT_ROOT/v5_dev_cache_manifest.json" || { echo 'Private V5 DEV cache missing' >&2; exit 2; }
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
remote_path = remote / 'v5_dev_cache_manifest.json'
assert remote_path.read_bytes() == locked_path.read_bytes(), 'DEV cache manifest changed'
manifest = json.loads(locked_path.read_text())
assert manifest['preregistration_commit'] == 'bca2f7ce26c8b741c124d878a714495b4897c789'
assert manifest['dataset_id'] == os.environ['DATASET_OWNER'] + '/' + os.environ['DATASET_SLUG']
archive = remote / manifest['archive_file']
if archive.is_file():
    assert archive.stat().st_size == manifest['archive_bytes']
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    assert digest.hexdigest() == manifest['archive_sha256'], 'DEV cache archive changed'
    cache_root = Path('/kaggle/working/locked_v5_dev')
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
    print('[V5 DEV input] compressed archive SHA verified')
else:
    candidates = [remote / 'v5_dev_cache', remote]
    matching = [path for path in candidates
                if all((path / 'dual_codec_search_v2' / codec / 'manifest.json').is_file()
                       for codec in ('h264', 'h265'))]
    assert len(matching) == 1, 'Kaggle DEV cache mount layout changed'
    cache_root = matching[0]
    print('[V5 DEV input] Kaggle-extracted cache found; runner checks every stage hash')
Path('/kaggle/working/v5_cache_root.txt').write_text(str(cache_root))
PY

cp configs/v5_dev_cache_manifest.json "$OUT/input_manifest.json"
CACHE_ROOT="$(cat /kaggle/working/v5_cache_root.txt)"
python -m ops.v5_dev_agreement \
  --h264-cache-root "$CACHE_ROOT/dual_codec_search_v2/h264" \
  --h265-cache-root "$CACHE_ROOT/dual_codec_search_v2/h265" \
  --out-dir "$OUT/results" 2>&1 | tee "$OUT/run.log"
test -s "$OUT/results/h264_result.json"
test -s "$OUT/results/h265_result.json"
echo '[done] V5 CAL/DEV only; no holdout or transfer-analyzer outcome'
