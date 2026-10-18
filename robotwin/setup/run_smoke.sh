#!/usr/bin/env bash
# Run one real policy episode and always stop the simulator we started.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 setup/preflight.py
test -f weights/model.safetensors
mkdir -p outputs
stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$(pwd)/outputs/$stamp"
mkdir "$run_dir"
# Refuse to reuse an unrelated service already listening on the starter port.
.venv-policy/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",8110)); s.close()'
.venv-sim/bin/python -u run_inference.py sim --robotwin-root "$(pwd)/RoboTwin" >"$run_dir/simulator.log" 2>&1 &
sim_pid=$!
trap 'kill "$sim_pid" 2>/dev/null || true; wait "$sim_pid" 2>/dev/null || true' EXIT
ready=0
for _ in $(seq 1 120); do
  kill -0 "$sim_pid" 2>/dev/null || { cat "$run_dir/simulator.log"; exit 1; }
  if .venv-policy/bin/python -c 'import socket; s=socket.create_connection(("127.0.0.1",8110), timeout=1); s.close()' 2>/dev/null; then ready=1; break; fi
  sleep 1
done
test "$ready" = 1 || { echo "Simulator readiness timed out: $run_dir/simulator.log"; exit 1; }
timeout 30m .venv-policy/bin/python -u run_inference.py policy --weights "$(pwd)/weights" --episodes 1 --seed "${1:-0}" --steps "${2:-1200}" --video-dir "$run_dir" 2>&1 | tee "$run_dir/policy.log"
grep -q 'success rate:' "$run_dir/policy.log"
test -s "$run_dir/episode_${1:-0}.mp4"
echo "Episode completed; see $run_dir. Completion does not mean task success."
