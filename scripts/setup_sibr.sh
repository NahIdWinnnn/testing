#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SIBR_SRC="$ROOT/methods/sibr_viewers"
SIBR_COMMIT="d8856f60c5384cc1975439193bb627d77d917d77"
SIBR_PATCHES=(
  "$ROOT/docs/patches/sibr_modern_linux_deps.patch"
  "$ROOT/docs/patches/sibr_var_test_pose_navigation.patch"
)
PATCH_MARKER=".var2026_test_pose_navigation"
SIBR_COMPAT="$ROOT/.local/sibr_compat"
WINDOWS_VIEWER=""
LINUX_VIEWER="$SIBR_SRC/install/bin/SIBR_gaussianViewer_app"
VIEWERS_ZIP="$ROOT/.local/sibr_download/viewers.zip"
VIEWERS_URL="https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/binaries/viewers.zip"
CUDA_CUDART_ZIP="$ROOT/.local/cuda_redist/cuda_cudart_windows_12.zip"
CUDA_CUDART_URL="https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/cuda_cudart-windows-x86_64-12.8.90-archive.zip"
BUILD_NATIVE=0

if [[ "${1:-}" == "--native" ]]; then
  BUILD_NATIVE=1
fi

cd "$ROOT"

git submodule update --init methods/sibr_viewers
git -C "$SIBR_SRC" fetch origin "$SIBR_COMMIT"
git -C "$SIBR_SRC" checkout "$SIBR_COMMIT"

update_env() {
  local viewer_path=$1
  local patched=${2:-0}
  conda run -n var2026 python -c '
from pathlib import Path
import sys

env = Path(".env")
updates = {
    "VAR2026_SIBR_GAUSSIAN_VIEWER": sys.argv[1],
    "VAR2026_SIBR_EXTRA_ARGS": "",
    "VAR2026_SIBR_PATCHED": sys.argv[2],
}
lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
seen = set()
output = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in updates:
        output.append(f"{key}={updates[key]}")
        seen.add(key)
    elif key != "VAR2026_DASHBOARD_PORT":
        output.append(line)
for key, value in updates.items():
    if key not in seen:
        output.append(f"{key}={value}")
env.write_text("\n".join(output) + "\n", encoding="utf-8")
' "$viewer_path" "$patched"
}

apply_sibr_patches() {
  local patch
  for patch in "${SIBR_PATCHES[@]}"; do
    if [[ ! -f "$patch" ]]; then
      echo "Error: missing SIBR patch: $patch" >&2
      exit 1
    fi
    if git -C "$SIBR_SRC" apply --reverse --check "$patch" >/dev/null 2>&1; then
      echo "SIBR patch already applied: $(basename "$patch")"
      continue
    fi
    git -C "$SIBR_SRC" apply "$patch"
    echo "Applied SIBR patch: $(basename "$patch")"
  done
}

prepare_linux_compat() {
  rm -rf "$SIBR_COMPAT"
  mkdir -p "$SIBR_COMPAT/include" "$SIBR_COMPAT/lib/cmake/embree-3.0"

  if [[ -d /usr/include/embree4 && ! -d /usr/include/embree3 ]]; then
    ln -s /usr/include/embree4 "$SIBR_COMPAT/include/embree3"
    cat > "$SIBR_COMPAT/lib/cmake/embree-3.0/embree-config.cmake" <<'EOF'
set(EMBREE_INCLUDE_DIRS "/usr/include")
set(EMBREE_LIBRARY "/usr/lib/x86_64-linux-gnu/libembree4.so")
set(EMBREE_LIBRARIES "${EMBREE_LIBRARY}")

if(NOT TARGET embree)
  add_library(embree SHARED IMPORTED)
  set_target_properties(embree PROPERTIES
    IMPORTED_LOCATION "${EMBREE_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${EMBREE_INCLUDE_DIRS}"
  )
endif()
EOF
    cat > "$SIBR_COMPAT/lib/cmake/embree-3.0/embree-config-version.cmake" <<'EOF'
set(PACKAGE_VERSION "3.0.0")
set(PACKAGE_VERSION_COMPATIBLE TRUE)
set(PACKAGE_VERSION_EXACT TRUE)
EOF
  fi
}

find_cuda_compiler() {
  if [[ -n "${CUDACXX:-}" ]]; then
    echo "$CUDACXX"
    return
  fi
  if command -v nvcc >/dev/null 2>&1; then
    command -v nvcc
    return
  fi
  local env_name=${VAR2026_GRAPHDECO_ENV:-graphdeco}
  if command -v conda >/dev/null 2>&1; then
    conda run -n "$env_name" bash -lc 'command -v nvcc' 2>/dev/null || true
  fi
}

find_cuda_host_compiler() {
  if [[ -n "${CUDAHOSTCXX:-}" ]]; then
    echo "$CUDAHOSTCXX"
    return
  fi
  local env_name=${VAR2026_GRAPHDECO_ENV:-graphdeco}
  if command -v conda >/dev/null 2>&1; then
    conda run -n "$env_name" bash -lc 'command -v x86_64-conda-linux-gnu-g++' 2>/dev/null || true
  fi
  if command -v g++-14 >/dev/null 2>&1; then
    command -v g++-14
    return
  fi
  if command -v g++-13 >/dev/null 2>&1; then
    command -v g++-13
    return
  fi
}

is_wsl() {
  [[ -n "${WSL_DISTRO_NAME:-}" ]] || grep -qi microsoft /proc/version 2>/dev/null
}

if is_wsl && [[ "$BUILD_NATIVE" != "1" ]]; then
  mkdir -p "$(dirname "$VIEWERS_ZIP")" "$ROOT/.local/sibr_windows"
  if [[ ! -f "$VIEWERS_ZIP" ]]; then
    wget -O "$VIEWERS_ZIP" "$VIEWERS_URL"
  fi
  mkdir -p "$(dirname "$CUDA_CUDART_ZIP")"
  if [[ ! -f "$CUDA_CUDART_ZIP" ]]; then
    wget -O "$CUDA_CUDART_ZIP" "$CUDA_CUDART_URL"
  fi
  conda run -n var2026 python -c '
from pathlib import Path
from zipfile import ZipFile

out = Path(".local/sibr_windows")
out.mkdir(parents=True, exist_ok=True)
ZipFile(".local/sibr_download/viewers.zip").extractall(out)

cuda_out = Path(".local/cuda_redist/cudart12")
cuda_out.mkdir(parents=True, exist_ok=True)
ZipFile(".local/cuda_redist/cuda_cudart_windows_12.zip").extractall(cuda_out)
'
  windows_profile=$(cmd.exe /c echo %USERPROFILE% | tr -d '\r' | tail -n 1)
  windows_profile_linux=$(wslpath -u "$windows_profile")
  windows_install="$windows_profile_linux/VAR2026/SIBR_viewers"
  rm -rf "$windows_install"
  mkdir -p "$windows_install"
  cp -a "$ROOT/.local/sibr_windows/." "$windows_install/"
  cudart=$(find "$ROOT/.local/cuda_redist/cudart12" -name cudart64_12.dll | head -n 1)
  if [[ -z "$cudart" ]]; then
    echo "Error: cudart64_12.dll was not found in CUDA runtime redistributable." >&2
    exit 1
  fi
  cp "$cudart" "$windows_install/bin/"
  chmod +x "$windows_install/bin"/*.exe
  WINDOWS_VIEWER="$windows_install/bin/SIBR_gaussianViewer_app.exe"
  if [[ ! -f "$WINDOWS_VIEWER" ]]; then
    echo "Error: SIBR Windows viewer was not found after extraction: $WINDOWS_VIEWER" >&2
    exit 1
  fi
  update_env "$WINDOWS_VIEWER" "0"
  echo "SIBR Windows viewer ready: $WINDOWS_VIEWER"
  echo "Mode: raw-sibr-fallback. For the VAR Test Poses panel, install native deps and run:"
  echo "  scripts/setup_sibr.sh --native"
  echo "Run: just viz <scene> graphdeco"
  exit 0
fi

apply_sibr_patches
prepare_linux_compat

deps=(
  cmake ninja-build libglew-dev libassimp-dev libboost-all-dev libgtk-3-dev
  libopencv-dev libglfw3-dev libavdevice-dev libavcodec-dev libeigen3-dev
  libxxf86vm-dev libembree-dev
)

if ! command -v cmake >/dev/null 2>&1; then
  if sudo -n true 2>/dev/null; then
    sudo apt update
    sudo apt install -y "${deps[@]}"
  else
    echo "SIBR native Linux build needs system packages." >&2
    echo "Run this once, then rerun scripts/setup_sibr.sh:" >&2
    echo "  sudo apt update && sudo apt install -y ${deps[*]}" >&2
    exit 1
  fi
fi

generator=()
if command -v ninja >/dev/null 2>&1; then
  generator=(-G Ninja)
fi

cuda_compiler=$(find_cuda_compiler | tail -n 1)
if [[ -z "$cuda_compiler" || ! -x "$cuda_compiler" ]]; then
  echo "SIBR native Gaussian viewer needs nvcc." >&2
  echo "Install CUDA toolkit or provide CUDACXX=/path/to/nvcc, then rerun scripts/setup_sibr.sh --native." >&2
  exit 1
fi
cuda_host_compiler=$(find_cuda_host_compiler | tail -n 1)
if [[ -z "$cuda_host_compiler" || ! -x "$cuda_host_compiler" ]]; then
  echo "SIBR native Gaussian viewer needs a CUDA-supported host C++ compiler." >&2
  echo "Install g++-14/g++-13, install conda gxx_linux-64 in the GraphDeCo env, or set CUDAHOSTCXX=/path/to/g++." >&2
  exit 1
fi
rm -f "$SIBR_SRC/build/CMakeCache.txt"
rm -rf "$SIBR_SRC/build/CMakeFiles"

cmake -S "$SIBR_SRC" -B "$SIBR_SRC/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_CUDA_COMPILER="$cuda_compiler" \
  -DCMAKE_CUDA_HOST_COMPILER="$cuda_host_compiler" \
  -DBoost_NO_BOOST_CMAKE=ON \
  -DCMAKE_POLICY_DEFAULT_CMP0167=OLD \
  -DBUILD_IBR_REMOTE=OFF \
  -Dembree_DIR="$SIBR_COMPAT/lib/cmake/embree-3.0" \
  -DCMAKE_CXX_FLAGS="-I$SIBR_COMPAT/include" \
  "${generator[@]}"
cmake --build "$SIBR_SRC/build" --target install -j "${MAX_JOBS:-$(nproc)}"

if [[ ! -f "$LINUX_VIEWER" ]]; then
  echo "Error: SIBR Linux viewer was not produced: $LINUX_VIEWER" >&2
  exit 1
fi
printf "VAR2026 SIBR test-pose navigation patch\n%s\n" "$SIBR_COMMIT" > "$SIBR_SRC/install/bin/$PATCH_MARKER"
update_env "methods/sibr_viewers/install/bin/SIBR_gaussianViewer_app" "1"
echo "SIBR Linux viewer ready: $LINUX_VIEWER"
echo "Mode: patched-sibr"
