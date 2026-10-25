#!/usr/bin/env bash
# 可选：把 Linux 版打包成单文件可执行程序（别人下载后双击即可，无需 Python 环境）
#
#   ./build-binary.sh
#
# 产物：dist/小黄桌宠   （约 60~90 MB，含 Python 运行时）
# 注意：必须在你自己的 Linux 机器上构建，Windows 上打不出 Linux 可执行文件。
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "=== 1/3 准备构建环境 ==="
BUILD_VENV="$HOME/.local/share/xiaohuang/build-venv"
if [ ! -x "$BUILD_VENV/bin/python" ]; then
  "$PY" -m venv "$BUILD_VENV"
fi
"$BUILD_VENV/bin/python" -m pip install --quiet --upgrade pip pyinstaller PyQt6 numpy

echo "=== 2/3 PyInstaller 打包 ==="
"$BUILD_VENV/bin/pyinstaller" \
  --noconfirm --clean --onefile \
  --name "小黄桌宠" \
  --add-data "小黄桌宠.py:." \
  小黄桌宠.py

echo "=== 3/3 完成 ==="
ls -lh dist/小黄桌宠
echo
echo "产物在 dist/小黄桌宠，把它和 素材.nwp 放在同一个文件夹即可运行："
echo "    ./dist/小黄桌宠"
echo "也可以把它上传到 GitHub Releases 供别人直接下载。"
