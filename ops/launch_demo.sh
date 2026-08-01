#!/usr/bin/env bash
# Quick launcher for local demo instances — starts one or all, health-checks
# them, and prints the URLs you actually need before a call.
#
# Usage:
#   ./launch_demo.sh              # start all known demos
#   ./launch_demo.sh lmtlss       # start just one
#   ./launch_demo.sh evolve
#
# Add a new client by adding one line to the CLIENTS array below.

set -euo pipefail
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../backend" && pwd)"
cd "$BACKEND_DIR"
source venv/bin/activate

# name|port|data_dir|widget_demo_page|sales_demo_file
CLIENTS=(
  "lmtlss|8000|./data|widget/demo.html|(none yet)"
  "evolve|8001|./data2|widget/demo_evolve.html|widget/evolve_live_demo.html"
)

start_one() {
  local name="$1" port="$2" data_dir="$3" widget_page="$4" sales_demo="$5"

  if curl -s "http://localhost:${port}/api/health" > /dev/null 2>&1; then
    echo "✓ ${name} already running on :${port}"
  else
    LEADGUARD_DATA_DIR="${data_dir}" nohup uvicorn app.main:app --port "${port}" \
      > "/tmp/leadguard_${name}.log" 2>&1 &
    for _ in $(seq 1 20); do
      sleep 0.3
      curl -s "http://localhost:${port}/api/health" > /dev/null 2>&1 && break
    done
    if curl -s "http://localhost:${port}/api/health" > /dev/null 2>&1; then
      echo "✓ ${name} started on :${port}"
    else
      echo "✗ ${name} failed to start — check /tmp/leadguard_${name}.log"
      return
    fi
  fi

  echo "    Dashboard:   http://localhost:${port}/dashboard/"
  echo "    Widget page: ${widget_page}"
  echo "    Sales demo:  ${sales_demo}"
  echo
}

target="${1:-all}"
found=0
for entry in "${CLIENTS[@]}"; do
  IFS='|' read -r name port data_dir widget_page sales_demo <<< "$entry"
  if [[ "$target" == "all" || "$target" == "$name" ]]; then
    found=1
    start_one "$name" "$port" "$data_dir" "$widget_page" "$sales_demo"
  fi
done

if [[ "$found" -eq 0 ]]; then
  echo "Unknown client '${target}'. Known: all, $(for e in "${CLIENTS[@]}"; do echo -n "${e%%|*} "; done)"
  exit 1
fi
