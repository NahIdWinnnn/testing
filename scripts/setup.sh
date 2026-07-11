#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
GRAPHDECO="$ROOT/methods/graphdeco"
RASTERIZER="$GRAPHDECO/submodules/diff-gaussian-rasterization"
CUDA_ARCH=${TORCH_CUDA_ARCH_LIST:-12.0}

cd "$ROOT"

if ! command -v conda >/dev/null 2>&1; then
  echo "Error: conda is not installed or not on PATH." >&2
  exit 1
fi

echo "[1/5] Install system packages"
sudo apt update
sudo apt install -y colmap libposelib just

echo "[2/5] Create or update var2026 env"
if conda env list | awk '{print $1}' | grep -qx var2026; then
  conda env update -n var2026 -f envs/var2026.yml --prune
else
  conda env create -f envs/var2026.yml
fi

echo "[3/5] Create or update graphdeco env"
if ! conda env list | awk '{print $1}' | grep -qx graphdeco; then
  conda create -n graphdeco python=3.10 -y
fi
conda run -n graphdeco python -m pip install -U pip setuptools wheel ninja cmake
conda run -n graphdeco python -m pip install \
  torch torchvision --index-url https://download.pytorch.org/whl/cu128
conda install -n graphdeco -c nvidia cuda-toolkit=12.8 -y
conda install -n graphdeco -c conda-forge \
  "gcc_linux-64=13.*" "gxx_linux-64=13.*" -y
conda run -n graphdeco python -m pip install \
  plyfile tqdm opencv-python joblib matplotlib scipy

echo "[4/5] Build GraphDeCo extensions"
PREFIX=$(conda run -n graphdeco python -c 'import sys; print(sys.prefix)')
CUDA_HOME="$PREFIX" \
TORCH_CUDA_ARCH_LIST="$CUDA_ARCH" \
MAX_JOBS="${MAX_JOBS:-4}" \
CC="$PREFIX/bin/x86_64-conda-linux-gnu-gcc" \
CXX="$PREFIX/bin/x86_64-conda-linux-gnu-g++" \
conda run -n graphdeco python -m pip install \
  "$GRAPHDECO/submodules/simple-knn" --no-build-isolation
CUDA_HOME="$PREFIX" \
TORCH_CUDA_ARCH_LIST="$CUDA_ARCH" \
MAX_JOBS="${MAX_JOBS:-4}" \
CC="$PREFIX/bin/x86_64-conda-linux-gnu-gcc" \
CXX="$PREFIX/bin/x86_64-conda-linux-gnu-g++" \
conda run -n graphdeco python -m pip install \
  "$RASTERIZER" --no-build-isolation

echo "[5/5] Check installation"
"$ROOT/scripts/doctor.sh"
