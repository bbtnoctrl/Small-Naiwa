#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 bbtnoctrl
# 把「小黄桌宠」装进 Linux 应用菜单（可选开机自启）
#
#   ./install.sh            装到应用菜单
#   ./install.sh --autostart    同时设置开机自启
#
# 卸载：
#   rm ~/.local/share/applications/xiaohuang.desktop
#   rm ~/.config/autostart/xiaohuang.desktop
set -e
cd "$(dirname "$0")"

HERE="$(pwd)"
RUN="$HERE/run.sh"
PY="$HERE/小黄桌宠.py"
ICON_SRC="$HERE/../形象/形象_245x312.png"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON="$ICON_DIR/xiaohuang.png"
APPS="$HOME/.local/share/applications"
AUTOSTART="$HOME/.config/autostart"

chmod +x "$RUN" "$PY" 2>/dev/null || true

mkdir -p "$ICON_DIR"
if [ -f "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$ICON"
else
  ICON="applications-games"
fi

DESKTOP_CONTENT="[Desktop Entry]
Type=Application
Name=小黄桌宠
Name[en]=XiaoHuang Desktop Pet
Comment=会转眼、眨眼、戳肚子、双击啄肚肚的桌面宠物
Exec=\"$RUN\"
Path=$HERE
Icon=$ICON
Terminal=false
Categories=Game;Amusement;
StartupNotify=false
"

mkdir -p "$APPS"
printf '%s' "$DESKTOP_CONTENT" > "$APPS/xiaohuang.desktop"
chmod +x "$APPS/xiaohuang.desktop"
echo "已安装到应用菜单：$APPS/xiaohuang.desktop"

if [ "$1" = "--autostart" ]; then
  mkdir -p "$AUTOSTART"
  printf '%s' "$DESKTOP_CONTENT" > "$AUTOSTART/xiaohuang.desktop"
  chmod +x "$AUTOSTART/xiaohuang.desktop"
  echo "已设置开机自启：$AUTOSTART/xiaohuang.desktop"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS" >/dev/null 2>&1 || true
fi

echo
echo "完成。之后在应用菜单里搜「小黄」就能启动，也可以直接运行："
echo "    $RUN"
