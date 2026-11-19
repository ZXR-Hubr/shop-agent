#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
HERE="$(pwd)"
echo "============================================"
echo " 小满商城 · 电商智能客服 Agent"
echo " 项目位置: $HERE"
echo " 启动后访问: http://127.0.0.1:8000"
echo " 按 Ctrl+C 停止服务"
echo "============================================"

PY="$HERE/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$HERE/.venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "[1/2] 首次运行，正在本目录创建虚拟环境 .venv ..."
  python3 -m venv .venv
  PY="$HERE/.venv/Scripts/python.exe"
  [ -x "$PY" ] || PY="$HERE/.venv/bin/python"
  echo "[2/2] 正在安装依赖到 .venv（PIP 缓存也放在项目目录）..."
  PIP_CACHE_DIR="$HERE/.pip-cache" "$PY" -m pip install -q -r requirements.txt
fi

echo "使用虚拟环境: $HERE/.venv"
exec "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
