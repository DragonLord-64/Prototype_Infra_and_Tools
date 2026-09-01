#!/bin/sh
set -e

/bin/node_exporter --web.listen-address=":${NODE_EXPORTER_PORT:-9100}" &
NODE_PID=$!

python3 /app/exporter.py &
PY_PID=$!

term_handler() {
    kill -TERM "$NODE_PID" "$PY_PID" 2>/dev/null
    wait "$NODE_PID" 2>/dev/null
    wait "$PY_PID" 2>/dev/null
    exit 0
}
trap term_handler TERM INT

while kill -0 "$NODE_PID" 2>/dev/null && kill -0 "$PY_PID" 2>/dev/null; do
    sleep 1
done

term_handler
