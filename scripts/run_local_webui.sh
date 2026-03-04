#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
HEALTH_PATH="${HEALTH_PATH:-/api/health}"
HEALTH_URL="http://${HOST}:${PORT}${HEALTH_PATH}"
STARTUP_TIMEOUT_SECONDS="${STARTUP_TIMEOUT_SECONDS:-10}"

cd "${ROOT_DIR}"

if [[ -x "${ROOT_DIR}/venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/venv/bin/python"
else
  PYTHON_BIN="python3"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[run_local_webui] curl 未安装，无法进行健康检查"
  exit 1
fi

is_healthy() {
  local url="$1"
  curl -fsS "${url}" >/dev/null 2>&1
}

listener_pid="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null | head -n1 || true)"
if [[ -n "${listener_pid}" ]]; then
  listener_cmd="$(ps -p "${listener_pid}" -o command= || true)"
  if is_healthy "${HEALTH_URL}"; then
    echo "[run_local_webui] 服务已运行: http://${HOST}:${PORT} (pid=${listener_pid})"
    exit 0
  fi

  if [[ "${listener_cmd}" == *"${ROOT_DIR}"* ]] || [[ "${listener_cmd}" == *"daily_stock_analysis"* ]]; then
    echo "[run_local_webui] 检测到项目旧进程占用端口，准备回收: pid=${listener_pid}"
    kill "${listener_pid}" || true
    sleep 1
  else
    echo "[run_local_webui] 端口 ${PORT} 被非本项目进程占用，未自动回收。"
    echo "[run_local_webui] pid=${listener_pid}, command=${listener_cmd}"
    exit 1
  fi
fi

echo "[run_local_webui] 启动服务 (稳定模式: WEBUI_AUTO_BUILD=false)"
WEBUI_AUTO_BUILD=false nohup "${PYTHON_BIN}" -m uvicorn api.app:app --host "${HOST}" --port "${PORT}" >/tmp/dsa8000.log 2>&1 &
new_pid="$!"
echo "[run_local_webui] 启动进程 pid=${new_pid}"

deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if is_healthy "${HEALTH_URL}"; then
    echo "[run_local_webui] 启动成功: http://${HOST}:${PORT}"
    exit 0
  fi
  sleep 1
done

echo "[run_local_webui] 启动超时，健康检查失败: ${HEALTH_URL}"
echo "[run_local_webui] 最近日志:"
tail -n 80 /tmp/dsa8000.log || true
exit 1
