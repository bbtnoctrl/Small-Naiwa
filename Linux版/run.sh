#!/usr/bin/env bash
# 小黄桌宠 · Linux 一键启动
#
#   ./run.sh            正常启动
#   ./run.sh --laugh    直接啄肚肚
#   ./run.sh --quit     让已运行的小黄退出
#
# 第一次运行如果系统里没有 PyQt6/numpy，会自动在
#   ~/.local/share/xiaohuang/venv
# 建一个独立环境装依赖（约 40 MB，只装一次，不污染系统 Python）。
set -e
cd "$(dirname "$0")"

APP="小黄桌宠.py"
VENV="$HOME/.local/share/xiaohuang/venv"
SYS_PY="${PYTHON:-python3}"

has_deps() {  # $1 = python 可执行文件
  "$1" -c "import PyQt6, numpy" >/dev/null 2>&1
}

# 1) 系统 Python 已经有依赖，直接用
if command -v "$SYS_PY" >/dev/null 2>&1 && has_deps "$SYS_PY"; then
  exec "$SYS_PY" "$APP" "$@"
fi

# 2) 之前装过独立环境，直接用
if [ -x "$VENV/bin/python" ] && has_deps "$VENV/bin/python"; then
  exec "$VENV/bin/python" "$APP" "$@"
fi

# 3) 首次运行：建环境 + 装依赖
if ! command -v "$SYS_PY" >/dev/null 2>&1; then
  echo "找不到 python3。请先安装：" >&2
  echo "    sudo apt install python3 python3-venv python3-pip" >&2
  exit 1
fi

echo "=== 小黄桌宠：首次运行，准备运行环境 ==="
echo "依赖会装到 $VENV（约 40 MB，只需一次）"
mkdir -p "$(dirname "$VENV")"

if ! "$SYS_PY" -m venv "$VENV" >/dev/null 2>&1; then
  echo "创建虚拟环境失败，通常是缺少 python3-venv：" >&2
  echo "    sudo apt install python3-venv" >&2
  exit 1
fi

"$VENV/bin/python" -m pip install --quiet --upgrade pip || true
if ! "$VENV/bin/python" -m pip install --quiet PyQt6 numpy; then
  echo "依赖安装失败。可以换国内镜像再试：" >&2
  echo "    $VENV/bin/python -m pip install PyQt6 numpy -i https://pypi.tuna.tsinghua.edu.cn/simple" >&2
  exit 1
fi

echo "=== 环境就绪，启动 ==="
exec "$VENV/bin/python" "$APP" "$@"
