#!/bin/bash
# Start the Zettelkasten API server (idempotent — safe to run if already running)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load .env for ZETTELKASTEN_BASE_DIR and other vars
if [ -f "${SCRIPT_DIR}/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "${SCRIPT_DIR}/.env"
    set +a
fi

LOGFILE="${ZETTELKASTEN_BASE_DIR:-${HOME}/Documents/SelfDevelopment}/logs/zettelkasten-api.log"
PORT=8000

if curl -s "http://127.0.0.1:${PORT}/health" | grep -q '"status":"ok"'; then
    echo "Zettelkasten API already running on port ${PORT}."
    exit 0
fi

echo "Starting Zettelkasten API on port ${PORT}..."
cd "${SCRIPT_DIR}" || exit 1
nohup python3 -m uvicorn main:app --host 127.0.0.1 --port "${PORT}" \
    >> "${LOGFILE}" 2>&1 &

sleep 2
if curl -s "http://127.0.0.1:${PORT}/health" | grep -q '"status":"ok"'; then
    echo "Started successfully. Logs: ${LOGFILE}"
else
    echo "Failed to start. Check: ${LOGFILE}"
    exit 1
fi
