#!/usr/bin/env bash
# Runs all automated tests (Linux). Needs: the venv (setup_linux.sh), g++ for the
# host simulation, socat for the backoff test. Add --live to hit Yahoo for real.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY=venv/bin/python
[[ -x "$PY" ]] || PY=python3
"$PY" -m py_compile ticker_bridge.py tests/*.py
"$PY" ticker_bridge.py --test
if command -v g++ >/dev/null; then
  g++ -std=c++17 -Wall -Wextra -I tests/host_sim/stubs -x c++ tests/host_sim/sim.cpp -o /tmp/ticker_sim
  /tmp/ticker_sim
else
  echo "g++ not found: skipping firmware host simulation"
fi
"$PY" tests/test_loopback.py "$@"
if command -v socat >/dev/null; then
  "$PY" tests/test_backoff_socat.py
else
  echo "socat not found: skipping backoff test"
fi
echo "ALL TESTS PASSED"
