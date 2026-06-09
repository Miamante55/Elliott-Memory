#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${OMBRE_BUCKETS_DIR:-/var/data/buckets}"
mkdir -p "${OMBRE_STATE_DIR:-/var/data/state}"

python server.py &
brain_pid=$!

python gateway.py &
gateway_pid=$!

nginx -g "daemon off;" &
nginx_pid=$!

shutdown() {
  kill "$brain_pid" "$gateway_pid" "$nginx_pid" 2>/dev/null || true
  wait "$brain_pid" "$gateway_pid" "$nginx_pid" 2>/dev/null || true
}

trap shutdown EXIT INT TERM
wait -n "$brain_pid" "$gateway_pid" "$nginx_pid"
