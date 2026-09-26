%%bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
REF="__REF__"
REPO=/kaggle/working/pre_processor
INDEX=/kaggle/working/kinetics_hash_split.json
OUT=/kaggle/working/outputs/paper_runtime_v2_full
mkdir -p "$OUT"
finish() {
  rc=$?
  trap - EXIT
  set +e
  cd /kaggle/working
  tar -czf paper_runtime_v2_full.tgz outputs/paper_runtime_v2_full \
    kinetics_hash_split.json runtime_input_check.json 2>/dev/null
  echo "[exit] rc=$rc artifact=/kaggle/working/paper_runtime_v2_full.tgz"
  exit "$rc"
}
trap finish EXIT
git clone -q https://github.com/munnn01/preeee.git "$REPO"
git -C "$REPO" checkout -q "$REF"
cd "$REPO"
python -c 'import psutil' || python -m pip install -q psutil==7.0.0
python -c 'import torch, torchvision, psutil, cv2; print("torch",torch.__version__,"torchvision",torchvision.__version__,"cuda",torch.cuda.is_available()); assert torch.cuda.is_available(), "GPU required for this benchmark"'
ffmpeg -hide_banner -encoders 2>/dev/null | grep -E 'libx264|libx265'
KIN_ROOT=""
for candidate in /kaggle/input/kineticscleaned /kaggle/input/datasets/qktttttttttt/kineticscleaned; do
  if [ -d "$candidate" ]; then KIN_ROOT="$candidate"; break; fi
done
test -n "$KIN_ROOT" || { echo 'Missing kineticscleaned dataset' >&2; exit 2; }
python scripts/build_train_index.py --root "$KIN_ROOT" --out "$INDEX" \
  --assert-fingerprint 30f083f8520a
export KIN_ROOT INDEX
python - <<'PY'
import hashlib
import json
import os
from pathlib import Path
source = json.loads(Path('configs/paper_runtime_dev/source_files.json').read_text())
sample_ids = json.loads(Path('configs/paper_runtime_dev/sample_ids.json').read_text())
index = json.loads(Path(os.environ['INDEX']).read_text())
by_id = {'/'.join(row['path'].replace('\\', '/').split('/')[-2:]): row
         for row in index['val']}
assert len(source) == len(sample_ids) == 20
assert [row['sequence_id'] for row in source] == sample_ids
for record in source:
    key = record['sequence_id']
    assert key in by_id, key
    path = Path(os.environ['KIN_ROOT']) / record['kaggle_path']
    assert path.exists(), path
    assert path.stat().st_size == record['bytes'], key
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], key
check = {'sample_ids': sample_ids,
         'sample_fingerprint': hashlib.sha256('\n'.join(sorted(sample_ids)).encode()).hexdigest(),
         'source_files_sha256': hashlib.sha256(Path('configs/paper_runtime_dev/source_files.json').read_bytes()).hexdigest(),
         'index_sha256': hashlib.sha256(Path(os.environ['INDEX']).read_bytes()).hexdigest(),
         'source_check': '20/20 SHA-256 matched'}
Path('/kaggle/working/runtime_input_check.json').write_text(json.dumps(check, indent=2))
print(check)
PY
for codec in h264 h265; do
  python -m ops.paper_runtime --codec "$codec" --index "$INDEX" \
    --split val --clips 20 \
    --sample-ids configs/paper_runtime_dev/sample_ids.json \
    --out-dir "$OUT/$codec" 2>&1 | tee "$OUT/${codec}.log"
  test -s "$OUT/$codec/runtime_result.json"
done
echo '[done] full 5-QP runtime for both codecs'
