#!/usr/bin/env bash
# 小黄桌宠 · Linux 启动脚本
# 用法： ./run.sh            正常启动
#        ./run.sh --laugh    直接啄肚肚
#        ./run.sh --quit     让已运行的小黄退出
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "找不到 $PY，请先安装 Python 3.9 以上版本" >&2
  exit 1
fi

if ! "$PY" -c "import PyQt6" >/dev/null 2>&1; then
  echo "缺少 PyQt6，请先执行：" >&2
  echo "    $PY -m pip install PyQt6" >&2
  echo "（Debian/Ubuntu 也可以用： sudo apt install python3-pyqt6）" >&2
  exit 1
fi

exec "$PY" 小黄桌宠.py "$@"
