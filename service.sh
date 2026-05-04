# SPDX-License-Identifier: MIT
#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#  Service manager (Linux/macOS) — mirrors service.bat workflow
#  Usage:
#    ./service.sh init   # pip + bundled SQL + optional Paddle warm-up
#    ./service.sh start  # start backend :8000 + frontend :8501 (no pip)
#    ./service.sh stop   # stop both
#    ./service.sh clear  # stop + remove project-local runtime artifacts
#
#  Optional env:
#    PIP_INDEX=https://pypi.org/simple
#    SVC_BACKEND_WAIT_SEC=45
# ============================================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGDIR="${ROOT}/logs"
STATEDIR="${ROOT}/.service"
BACKEND_PID="${STATEDIR}/backend.pid"
FRONTEND_PID="${STATEDIR}/frontend.pid"
BACKEND_LOG="${LOGDIR}/backend.stdout.log"
FRONTEND_LOG="${LOGDIR}/frontend.stdout.log"

: "${PIP_INDEX:=https://pypi.tuna.tsinghua.edu.cn/simple}"
: "${PIP_FALLBACK:=https://pypi.org/simple}"
: "${SVC_BACKEND_WAIT_SEC:=45}"

PY=""

svc_log() {
  ensure_dirs
  # Best-effort: do not fail service because of log write.
  local msg="$*"
  printf '[%(%Y-%m-%d %H:%M:%S)T] [service] %s\n' -1 "${msg}" >>"${LOGDIR}/app.log" 2>/dev/null || true
}

ensure_dirs() {
  mkdir -p "${LOGDIR}" "${STATEDIR}"
}

resolve_python() {
  if command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PY="$(command -v python)"
  else
    echo "[ERROR] python3/python not found" >&2
    return 1
  fi

  "${PY}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1 || {
    echo "[ERROR] Python 3.10+ required" >&2
    return 1
  }
}

pip_install() {
  resolve_python
  svc_log "init: pip install begin"
  echo "Installing python dependencies..."
  if ! "${PY}" -m pip install -r "${ROOT}/requirements.txt" -i "${PIP_INDEX}"; then
    echo "[WARN] Mirror failed, retrying PyPI..."
    "${PY}" -m pip install -r "${ROOT}/requirements.txt" -i "${PIP_FALLBACK}"
  fi
  svc_log "init: pip install done"
}

kill_by_pidfiles() {
  ensure_dirs
  if [[ -f "${BACKEND_PID}" ]]; then
    kill "$(cat "${BACKEND_PID}")" >/dev/null 2>&1 || true
    rm -f "${BACKEND_PID}"
  fi
  if [[ -f "${FRONTEND_PID}" ]]; then
    kill "$(cat "${FRONTEND_PID}")" >/dev/null 2>&1 || true
    rm -f "${FRONTEND_PID}"
  fi
}

kill_by_ports() {
  # Best-effort. Prefer lsof; fall back to fuser.
  for port in 8000 8501; do
    if command -v lsof >/dev/null 2>&1; then
      local pids
      pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "${pids}" ]]; then
        # shellcheck disable=SC2086
        kill ${pids} >/dev/null 2>&1 || true
      fi
    elif command -v fuser >/dev/null 2>&1; then
      fuser -k "${port}"/tcp >/dev/null 2>&1 || true
    fi
  done
}

wait_for_port() {
  local port="$1"
  local timeout="$2"
  resolve_python
  "${PY}" - <<PY
import socket, time, sys
host = "127.0.0.1"
port = int(${port})
timeout = float(${timeout})
deadline = time.time() + timeout
while time.time() < deadline:
    s = socket.socket()
    s.settimeout(0.3)
    try:
        s.connect((host, port))
        sys.exit(0)
    except OSError:
        time.sleep(0.3)
    finally:
        try: s.close()
        except Exception: pass
sys.exit(1)
PY
}

stop() {
  ensure_dirs
  svc_log "stop: begin"
  echo "Stopping services..."
  kill_by_pidfiles
  kill_by_ports
  svc_log "stop: done"
  echo "Done."
}

start_backend() {
  resolve_python
  echo "Starting backend (8000)..."
  (cd "${ROOT}" && \
    export PYTHONPATH="${ROOT}/src" && \
    export PYTHONUNBUFFERED=1 && \
    nohup "${PY}" -u -m uvicorn recognizer.interfaces.api.app:app --host 127.0.0.1 --port 8000 \
      >"${BACKEND_LOG}" 2>&1 & echo $! >"${BACKEND_PID}") || return 1
}

start_frontend() {
  resolve_python
  echo "Starting frontend (8501)..."
  (cd "${ROOT}" && \
    export PYTHONPATH="${ROOT}/src" && \
    export PYTHONUNBUFFERED=1 && \
    nohup "${PY}" -u -m streamlit run src/recognizer/interfaces/web/app.py \
      --server.port 8501 --server.headless true --browser.gatherUsageStats false \
      >"${FRONTEND_LOG}" 2>&1 & echo $! >"${FRONTEND_PID}") || return 1
}

dev_backend() {
  # Foreground dev mode
  resolve_python
  : "${HOST:=127.0.0.1}"
  : "${PORT:=8000}"
  export PYTHONPATH="${ROOT}/src"
  export PYTHONUNBUFFERED=1
  exec "${PY}" -u -m uvicorn recognizer.interfaces.api.app:app --host "${HOST}" --port "${PORT}"
}

dev_frontend() {
  # Foreground dev mode
  resolve_python
  : "${PORT:=8501}"
  export PYTHONPATH="${ROOT}/src"
  export PYTHONUNBUFFERED=1
  exec "${PY}" -u -m streamlit run "${ROOT}/src/recognizer/interfaces/web/app.py" \
    --server.port "${PORT}" \
    --server.headless true \
    --browser.gatherUsageStats false
}

start() {
  ensure_dirs
  svc_log "start: begin"
  echo "Stopping existing listeners..."
  kill_by_pidfiles
  kill_by_ports
  sleep 1
  echo "Done."

  start_backend
  echo "Waiting for backend :8000 (max ${SVC_BACKEND_WAIT_SEC}s)..."
  if ! wait_for_port 8000 "${SVC_BACKEND_WAIT_SEC}"; then
    svc_log "[ERROR] backend not listening"
    echo "[ERROR] Backend failed (8000). See ${LOGDIR}/app.log and ${BACKEND_LOG}"
    stop
    exit 1
  fi

  start_frontend
  # Frontend usually starts quickly; keep a small wait but don't block too long.
  wait_for_port 8501 45 >/dev/null 2>&1 || true

  svc_log "start: done"
  echo ""
  echo "Service Started!"
  echo "  Frontend: http://127.0.0.1:8501"
  echo "  API Docs: http://127.0.0.1:8000/docs"
  echo "  Log file: ${LOGDIR}/app.log"
}

init() {
  ensure_dirs
  svc_log "init: begin"
  pip_install

  echo "Initializing database (data/db/scripts)..."
  resolve_python
  if ! "${PY}" -m recognizer.infrastructure.local_runtime.initial_bootstrap; then
    svc_log "[ERROR] database init failed"
    echo "[ERROR] Database initialization failed."
    exit 1
  fi

  echo "PaddleOCR warm-up (ocr.prefetch_on_init in settings.yaml)..."
  if ! "${PY}" -m recognizer.infrastructure.ocr.warm_paddle; then
    svc_log "[WARN] PaddleOCR warm-up during init failed"
    echo "[WARN] Paddle warm-up failed (offline or network). Start may retry download. See ${LOGDIR}/app.log"
  fi

  svc_log "init: done"
  echo "Init complete. Run: ./service.sh start"
}

clear() {
  ensure_dirs
  svc_log "clear: begin"
  echo "Clear: stopping services..."
  kill_by_pidfiles
  kill_by_ports
  sleep 1
  echo "Clear: removing project-local runtime files (database, OCR model dirs under config, logs, .service — not pip packages)..."

  resolve_python
  if ! "${PY}" -m recognizer.infrastructure.local_runtime.clear_local_runtime; then
    svc_log "[ERROR] clear db step failed"
    echo "[ERROR] clear failed (database step)."
    exit 1
  fi

  rm -f "${LOGDIR}"/* 2>/dev/null || true
  rm -f "${STATEDIR}"/* 2>/dev/null || true
  rm -f "${ROOT}/test_seed.db" 2>/dev/null || true
  svc_log "clear: done"
  echo "Clear complete. Next: ./service.sh init"
}

cmd="${1:-}"
case "${cmd}" in
  init) init ;;
  start) start ;;
  stop) stop ;;
  clear) clear ;;
  backend) dev_backend ;;
  frontend) dev_frontend ;;
  *)
    echo "Usage:"
    echo "  ./service.sh init"
    echo "  ./service.sh start"
    echo "  ./service.sh stop"
    echo "  ./service.sh clear"
    echo ""
    echo "Dev (foreground):"
    echo "  HOST=127.0.0.1 PORT=8000 ./service.sh backend"
    echo "  PORT=8501 ./service.sh frontend"
    exit 1
    ;;
esac

