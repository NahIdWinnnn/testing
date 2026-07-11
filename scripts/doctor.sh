#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

echo "COLMAP"
colmap -h >/dev/null
echo "  OK"

echo "var2026"
conda run -n var2026 python -m var2026 --help >/dev/null
echo "  OK"

echo "GraphDeCo"
conda run -n graphdeco python -c \
  "import torch, simple_knn, diff_gaussian_rasterization; assert torch.cuda.is_available(); print('  GPU:', torch.cuda.get_device_name(0)); print('  CUDA:', torch.version.cuda)"

if [[ -d VAI_NVS_DATA/phase1/public_set ]]; then
  echo "Dataset"
  echo "  OK"
else
  echo "Dataset"
  echo "  Not found. Put VAI_NVS_DATA in the repository before training."
fi

echo "Setup OK"
