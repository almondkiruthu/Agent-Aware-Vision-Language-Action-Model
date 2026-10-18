#!/usr/bin/env bash
# Staged installation: never download large assets before the renderer works.
set -euo pipefail
cd "$(dirname "$0")/.."
stage="${1:-check}"
case "$stage" in
check)
  python3 setup/preflight.py
  ;;
environments)
  python3 setup/preflight.py
  command -v uv >/dev/null || { echo 'Install uv from https://docs.astral.sh/uv/ first.'; exit 1; }
  test -x .venv-sim/bin/python || uv venv --python 3.10 .venv-sim
  uv pip install --python .venv-sim/bin/python numpy==1.26.4 sapien==3.0.3 imageio
  .venv-sim/bin/python setup/render_smoke.py
  uv pip install --python .venv-sim/bin/python torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
  uv pip install --python .venv-sim/bin/python -r requirements-sim.txt -c setup/sim-constraints.txt
  test -x .venv-policy/bin/python || uv venv --python 3.12 .venv-policy
  uv pip install --python .venv-policy/bin/python -r requirements-policy.txt
  ;;
source)
  revision=$(python3 -c 'import json; print(json.load(open("setup/pins.json"))["robotwin"])')
  if [ ! -d RoboTwin ]; then
    git clone --no-checkout https://github.com/RoboTwin-Platform/RoboTwin.git RoboTwin
    git -C RoboTwin checkout "$revision"
    git -C RoboTwin submodule update --init --recursive
  elif [ -d RoboTwin/.git ]; then
    test "$(git -C RoboTwin rev-parse HEAD)" = "$revision" || { echo 'RoboTwin revision mismatch'; exit 1; }
    git -C RoboTwin submodule update --init --recursive
  else
    test "$(cat RoboTwin/.source-revision)" = "$revision" || { echo 'Archive revision mismatch'; exit 1; }
    echo 'Using pinned archive snapshot. XPolicyLab is omitted; this starter uses its separately pinned LeRobot policy.'
  fi
  ;;
curobo)
  : "${CUDA_HOME:?Set CUDA_HOME to the CUDA 12.x development toolkit}"
  test -f "$CUDA_HOME/include/cuda_runtime_api.h"
  "$CUDA_HOME/bin/nvcc" --version | grep -q 'release 12\.'
  compiler="${CXX:-g++}"
  test "$("$compiler" -dumpversion | cut -d. -f1)" -ge 13 || { echo 'Client requires GCC/G++ >=13'; exit 1; }
  if [ ! -d RoboTwin/envs/curobo ]; then
    git clone --branch v0.7.8 --depth 1 https://github.com/NVlabs/curobo.git RoboTwin/envs/curobo
  fi
  uv pip install --python .venv-sim/bin/python 'setuptools<81' wheel ninja packaging
  MAX_JOBS=2 uv pip install --python .venv-sim/bin/python -e RoboTwin/envs/curobo --no-build-isolation
  uv pip install --python .venv-sim/bin/python warp-lang==1.12.0
  .venv-sim/bin/python setup/patch_runtime.py
  ;;
assets)
  python3 setup/preflight.py
  .venv-sim/bin/python setup/render_smoke.py
  .venv-sim/bin/python setup/download_assets.py
  ;;
weights)
  .venv-policy/bin/python setup/download_checkpoint.py
  ;;
*) echo 'Usage: bash setup/install_linux.sh check|environments|source|curobo|assets|weights'; exit 2 ;;
esac
