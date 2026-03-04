#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/apps/dsa-web"

if ! command -v npm >/dev/null 2>&1; then
  echo "[build_frontend] 未检测到 npm，请先安装 Node.js"
  exit 1
fi

cd "${FRONTEND_DIR}"
echo "[build_frontend] npm install"
npm install
echo "[build_frontend] npm run build"
npm run build
echo "[build_frontend] 前端构建完成"
