#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小黄桌宠 · Linux 版

读取与 Windows 版相同的 素材.nwp（就是 zip + PNG），在 X11 / Wayland 桌面上显示一只
会转眼睛、会眨眼、能戳肚子、双击会啄肚肚的小黄。

依赖：PyQt6、Pillow（只用 Pillow 读 metadata 的地方可以省掉，实际不需要）
运行：python3 小黄桌宠.py            正常启动
      python3 小黄桌宠.py --laugh    启动后直接啄肚肚（给脚本/插件调用）
      python3 小黄桌宠.py --quit     通知已在运行的实例退出

素材目录查找顺序：
  1) --assets 参数指定的路径
  2) 与本脚本同目录的 素材.nwp
  3) 与脚本同目录的上一级目录里的 素材.nwp（比如放在仓库的 Linux版/ 子目录里）
"""

import json
import math
import time
import os
import random
import subprocess
import sys
import zipfile
from collections import OrderedDict

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    np = None
    HAS_NUMPY = False

from PyQt6.QtCore import QPoint, QPointF, QRectF, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import (QAction, QColor, QCursor, QGuiApplication, QIcon, QImage,
                         QPainter, QPixmap, QTransform)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

APP_NAME = "小黄桌宠"
WIN_TITLE = "XiaoHuangDesktop.v1"
LOCAL_SERVER = "xiaohuang-linux-v1"
SETTINGS_ORG = "XiaoHuangPet"

# 与 Windows 版保持一致的画布内坐标（245x312 画布下的肚子椭圆）
BELLY_CX, BELLY_CY = 122.0, 206.0
BELLY_RX, BELLY_RY = 86.0, 76.0
EYE_HIT = 110.0          # 鼠标离眼睛多远算"看到最边上"
GAZE_TAU = 0.13          # 眼球跟随平滑时间常数（秒）
SCALES = [0.75, 1.0, 1.25]
POKE_DURATION = 0.95          # 与 Windows 版一致
LAND_DURATION = 0.90
POKE_RX, POKE_RY = 98.0, 86.0 # 戳肚子影响的椭圆半径（画布坐标）
POKE_TOP, POKE_BOTTOM = 127.0, 291.0
POKE_NECK, POKE_LEGS = 28.0, 22.0
SCALE_NAMES = ["小号", "标准", "大号"]


# ---------------------------------------------------------------- 素材加载
class Assets:
    """把 素材.nwp 读进内存，按需解码成 QImage（带 LRU 缓存）。"""

    def __init__(self, path):
        self.zip = zipfile.ZipFile(path)
        names = set(self.zip.namelist())
        self.meta = json.loads(self.zip.read("metadata.json").decode("utf-8-sig"))
        self.w = int(self.meta["width"])
        self.h = int(self.meta["height"])
        self.frames = int(self.meta.get("frames", 0))
        self.fps = float(self.meta.get("fps", 30))
        self.eye_frames = int(self.meta.get("eyeFrames", 2))
        self.blink_frames = int(self.meta.get("blinkFrames", 7))
        self.blink_fps = float(self.meta.get("blinkFps", 30))
        self.pupil_range = int(self.meta.get("pupilRange", 0))
        self.pupil_range2 = int(self.meta.get("pupilRange2", self.pupil_range))
        self.eye_x = float(self.meta.get("eyeX", self.w * 0.5))
        self.eye_y = float(self.meta.get("eyeY", self.h * 0.4))

        self.has_pupil = "pupil/00.png" in names
        self.has_pupil2 = "pupil2/00.png" in names
        self.laugh_names = sorted(n for n in names if n.startswith("laugh/") and n.endswith(".png"))
        self.look_names = sorted(n for n in names if n.startswith("look/") and n.endswith(".png"))
        self._cache = OrderedDict()
        self._cache_max = 64

    # -- 底层取图
    def _image(self, name):
        if name in self._cache:
            self._cache.move_to_end(name)
            return self._cache[name]
        try:
            data = self.zip.read(name)
        except KeyError:
            return None
        img = QImage()
        img.loadFromData(data, "PNG")
        if img.isNull():
            return None
        img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self._cache[name] = img
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)
        return img

    @property
    def base(self):
        return self._image("base/00.png")

    @property
    def pupil(self):
        return self._image("pupil/00.png") if self.has_pupil else None

    @property
    def pupil2(self):
        return self._image("pupil2/00.png") if self.has_pupil2 else None

    def look(self, idx):
        if not self.look_names:
            return self.base
        idx = max(0, min(len(self.look_names) - 1, idx))
        return self._image(self.look_names[idx])

    def blink(self, bank, idx):
        idx = max(0, min(self.blink_frames - 1, idx))
        return self._image("blink/%d/%02d.png" % (1 if bank else 0, idx))

    def laugh(self, idx):
        if not self.laugh_names:
            return self.base
        idx = max(0, min(len(self.laugh_names) - 1, idx))
        return self._image(self.laugh_names[idx])

    @property
    def laugh_count(self):
        return len(self.laugh_names)


# ---------------------------------------------------------------- 主窗口
class Pet(QWidget):
    def __init__(self, assets, app):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.setMouseTracking(True)
        self.setWindowTitle(WIN_TITLE)

        self.a = assets
        self.app = app
        self.cfg = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                             SETTINGS_ORG, "settings")

        # 状态
        self.scale_idx = int(self.cfg.value("scale", 1))
        self.scale = SCALES[max(0, min(len(SCALES) - 1, self.scale_idx))]
        self.on_top = self.cfg.value("ontop", "true") in (True, "true")
        self.hide_fullscreen = self.cfg.value("hidefs", "true") in (True, "true")

        self.look_x = 0.0
        self.look_y = 0.0
        self.blink_start = -1.0
        self.next_blink = 4.0
        self.laugh_start = -1.0

        # 以下全部沿用 Windows 版 Motion / Renderer 的变量与公式
        self.poke_start = -1.0      # 戳肚子开始时间
        self.poke_x = BELLY_CX      # 点击位置（画布坐标，接触点即变形中心）
        self.poke_y = BELLY_CY
        self.land_start = -1.0      # 松手落地弹跳
        self.holding = False        # 按住未松手
        self.drag_angle = 0.0       # 拖动倾斜角
        self.drag_vel = 0.0
        self.drag_target = 0.0
        self.last_drag_t = 0.0
        self.dragging = False
        self.drag_off = QPoint()
        self.fs_hidden = False
        self.hidden_by_fs = False
        self.composite_key = None
        self.composite = None
        self._poke_cache = {}
        self.t0 = time.monotonic()
        self._last_t = 0.0

        self.resize(self._win_size())
        self._restore_pos()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

        self._build_menu()
        self._build_tray()

        self.fs_timer = QTimer(self)
        self.fs_timer.timeout.connect(self._check_fullscreen)
        if self.hide_fullscreen and QGuiApplication.platformName() == "xcb":
            self.fs_timer.start(2000)

    # -- 时间
    @property
    def clock(self):
        return time.monotonic() - self.t0

    # -- 几何
    def _win_size(self):
        return QSize(int(round(self.a.w * self.scale)), int(round(self.a.h * self.scale)))

    def _restore_pos(self):
        sx = self.cfg.value("x", None)
        sy = self.cfg.value("y", None)
        if sx is not None and sy is not None:
            self.move(int(sx), int(sy))
        else:
            self.home()

    def home(self):
        scr = self.screen() or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        self.move(g.right() - self.width() - int(40 * self.scale),
                  g.bottom() - self.height() + 1)
        self._save_pos()

    def _save_pos(self):
        self.cfg.setValue("x", self.x())
        self.cfg.setValue("y", self.y())

    # -- 菜单 / 托盘
    def _build_menu(self):
        self.menu = QMenu()
        self.menu.addAction("啄肚肚（双击）", self.start_laugh)
        self.stop_action = QAction("停止啄肚肚 / 站起来", self, triggered=self.stop_laugh)
        self.menu.addAction(self.stop_action)
        self.menu.addSeparator()

        size_menu = self.menu.addMenu("大小")
        for i, nm in enumerate(SCALE_NAMES):
            act = QAction(nm, self, checkable=True, checked=(i == self.scale_idx))
            act.triggered.connect(lambda _=False, k=i: self.set_scale(k))
            size_menu.addAction(act)
        self.size_menu = size_menu

        self.ontop_action = QAction("总在最上面", self, checkable=True, checked=self.on_top)
        self.ontop_action.triggered.connect(self.set_on_top)
        self.menu.addAction(self.ontop_action)

        self.fs_action = QAction("全屏时自动隐藏", self, checkable=True, checked=self.hide_fullscreen)
        self.fs_action.triggered.connect(self.set_hide_fs)
        self.menu.addAction(self.fs_action)

        self.menu.addAction("回到屏幕右下角", self.home)
        self.menu.addSeparator()
        self.menu.addAction("打开使用说明", self.open_help)
        self.menu.addAction("退出小黄", self.quit)

    def _build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon_img = self._tray_image()
        self.tray = QSystemTrayIcon(QIcon(QPixmap.fromImage(icon_img)), self)
        self.tray.setToolTip("小黄 · 双击啄肚肚 / 拖动")
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_image(self):
        """从 look/00 里裁出头部当托盘图标（和 Windows 版同一块区域）。"""
        src = self.a.look(0) or self.a.base
        if src is None:
            return QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
        fx = src.width() / float(self.a.w)
        r = QRectF(45 * fx, 31 * fx, 154 * fx, 190 * fx)
        cut = src.copy(r.toRect()).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
        out = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(QColor(0, 0, 0, 0))
        p = QPainter(out)
        p.drawImage((64 - cut.width()) // 2, (64 - cut.height()) // 2, cut)
        p.end()
        return out

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.home()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.menu.popup(QCursor.pos())

    # -- 设置项
    def set_scale(self, idx):
        old_ratio = (self.x() + self.width() / 2) / max(1, self.width())
        self.scale_idx = idx
        self.scale = SCALES[idx]
        self.cfg.setValue("scale", idx)
        self.resize(self._win_size())
        for act in self.size_menu.actions():
            act.setChecked(act.text() == SCALE_NAMES[idx])
        self.composite_key = None

    def set_on_top(self, checked):
        self.on_top = bool(checked)
        self.cfg.setValue("ontop", "true" if self.on_top else "false")
        flags = self.windowFlags()
        if self.on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def set_hide_fs(self, checked):
        self.hide_fullscreen = bool(checked)
        self.cfg.setValue("hidefs", "true" if self.hide_fullscreen else "false")

    def open_help(self):
        for d in app_dirs():
            cand = os.path.join(d, "使用说明.txt")
            if os.path.exists(cand):
                os.system('xdg-open "%s" >/dev/null 2>&1 &' % cand)
                return

    def quit(self):
        self._save_pos()
        if self.tray:
            self.tray.hide()
        self.app.quit()

    # -- 动作
    def start_laugh(self):
        if self.laugh_start >= 0:
            return
        self.laugh_start = self.clock
        self.next_blink = self.clock + 3.0

    def stop_laugh(self):
        if self.laugh_start >= 0:
            self.laugh_start = -1
            self.next_blink = self.clock + 1.0

    def poke(self, pos=None):
        """和 Windows 版一样：按下的位置就是变形中心。"""
        self.poke_start = self.clock
        if pos is not None:
            self.poke_x = pos.x() / self.scale
            self.poke_y = pos.y() / self.scale
        self.blink_start = -1.0

    # -- 和 Windows 版一致的派生量
    @property
    def poking(self):
        return self.poke_start >= 0

    @property
    def poke_amount(self):
        if not self.poking:
            return 0.0
        t = self.clock - self.poke_start
        if t < 0 or t >= POKE_DURATION:
            return 0.0
        if t < 0.12:
            return 0.60 * math.sin(t / 0.12 * math.pi / 2)
        return 0.60 * math.exp(-4.8 * (t - 0.12)) * math.cos(18 * (t - 0.12))

    @property
    def landing(self):
        return self.land_start >= 0

    @property
    def squash(self):
        if not self.landing:
            return 0.0
        t = self.clock - self.land_start
        if t < 0:
            return 0.0
        return 0.055 * math.exp(-6 * t) * math.sin(19 * t)

    @property
    def moving(self):
        return self.holding or self.landing or abs(self.drag_angle) > 0.02

    # -- 命中判断
    def in_belly(self, pos):
        cx = BELLY_CX * self.scale
        cy = BELLY_CY * self.scale
        dx = (pos.x() - cx) / (BELLY_RX * self.scale)
        dy = (pos.y() - cy) / (BELLY_RY * self.scale)
        return dx * dx + dy * dy <= 1.0

    # -- 事件
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.menu.popup(e.globalPosition().toPoint())
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.dragging = False
        self.drag_off = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        self.down_pos = e.position().toPoint()
        self.down_global = e.globalPosition().toPoint()
        self.down_time = self.clock
        # Windows 版是按下就戳（InBelly 判定），双击时 Laugh 会把它清掉
        if not self.laugh_start >= 0 and self.in_belly(self.down_pos):
            self.poke(self.down_pos)
        self.holding = True
        self.last_drag_t = self.clock
        e.accept()

    def mouseMoveEvent(self, e):
        gpos = e.globalPosition().toPoint()
        if not (e.buttons() & Qt.MouseButton.LeftButton):
            return
        if not self.dragging:
            if (gpos - getattr(self, "down_global", gpos)).manhattanLength() > 4:
                self.dragging = True
        if self.dragging:
            self.move(gpos - self.drag_off)
            dt = max(1.0 / 120.0, self.clock - self.last_drag_t)
            last_x = getattr(self, "_last_gx", gpos.x())
            dx = gpos.x() - last_x
            self._last_gx = gpos.x()
            self.last_drag_t = self.clock
            self.drag_target = max(-7.0, min(7.0, dx / dt * 0.013))
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.holding = False
        self.drag_target = 0.0
        if self.dragging:
            self.dragging = False
            self._save_pos()
            self.home_clamp()
        self.land_start = self.clock      # Windows 版同样在松手时开始落地
        e.accept()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.poke_start = -1.0        # 双击取消戳肚子
            self.start_laugh()
            e.accept()

    def home_clamp(self):
        scr = self.screen() or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        x = max(g.left() - self.width() // 3, min(self.x(), g.right() - self.width() // 2))
        y = max(g.top(), min(self.y(), g.bottom() - 20))
        self.move(x, y)
        self._save_pos()

    # -- 全屏自动隐藏（仅 X11 有效）
    def _check_fullscreen(self):
        if not self.hide_fullscreen:
            if self.fs_hidden:
                self.show()
                self.fs_hidden = False
            return
        try:
            out = subprocess.run(["xdotool", "getactivewindow", "getwindowgeometry", "--shell"],
                                 capture_output=True, text=True, timeout=2)
        except Exception:
            self.fs_timer.stop()      # 没有 xdotool 就不再检测
            return
        geo = {}
        for line in out.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                geo[k.strip()] = v.strip()
        if "WIDTH" not in geo or "HEIGHT" not in geo:
            return
        w = int(geo["WIDTH"]); h = int(geo["HEIGHT"])
        scr = (self.screen() or QGuiApplication.primaryScreen()).geometry()
        fullscreen = w >= scr.width() - 2 and h >= scr.height() - 2
        if fullscreen and not self.fs_hidden:
            if self.laugh_start >= 0:
                self.stop_laugh()
            self.hide()
            self.fs_hidden = True
        elif not fullscreen and self.fs_hidden:
            self.show()
            self.fs_hidden = False

    # -- 每帧
    def _tick(self):
        now = self.clock
        dt = min(0.1, max(0.001, now - self._last_t)) if self._last_t else 0.016
        self._last_t = now

        # 眼球跟随
        if not self.dragging and self.laugh_start < 0:
            gp = QCursor.pos()
            local = self.mapFromGlobal(gp)
            ex = self.a.eye_x * self.scale
            ey = self.a.eye_y * self.scale
            dx = local.x() - ex
            dy = local.y() - ey
            dist = math.hypot(dx, dy)
            mag = min(1.0, dist / EYE_HIT)
            tx = (dx / dist * mag) if dist > 1e-3 else 0.0
            ty = (dy / dist * mag) if dist > 1e-3 else 0.0
            k = min(1.0, dt / GAZE_TAU)
            self.look_x += (tx - self.look_x) * k
            self.look_y += (ty - self.look_y) * k
        else:
            k = min(1.0, dt / GAZE_TAU)
            self.look_x += (0 - self.look_x) * k
            self.look_y += (0 - self.look_y) * k

        # 眨眼
        if self.blink_start < 0 and self.laugh_start < 0 and self.clock >= self.next_blink:
            self.blink_start = self.clock
        if self.blink_start >= 0:
            if (self.clock - self.blink_start) * self.a.blink_fps >= self.a.blink_frames:
                self.blink_start = -1
                self.next_blink = self.clock + random.uniform(4.0, 8.0)

        # 拖动倾斜：和 Windows 版同一套弹簧（160 刚度 / 25 阻尼 / ±7°）
        if not self.holding or (now - self.last_drag_t > 0.10):
            self.drag_target = 0.0
        steps = 3
        st = dt / steps
        for _ in range(steps):
            self.drag_vel += (160.0 * (self.drag_target - self.drag_angle) - 25.0 * self.drag_vel) * st
            self.drag_angle += self.drag_vel * st
        self.drag_angle = max(-7.0, min(7.0, self.drag_angle))
        if (not self.holding) and abs(self.drag_angle) < 0.02 and abs(self.drag_vel) < 0.05:
            self.drag_angle = 0.0
            self.drag_vel = 0.0

        # 计时结束（与 Windows 版一致的时长）
        if self.landing and now - self.land_start >= LAND_DURATION:
            self.land_start = -1.0
        if self.poking and now - self.poke_start >= POKE_DURATION:
            self.poke_start = -1.0

        # 啄肚肚结束
        if self.laugh_start >= 0:
            dur = self.a.laugh_count / self.a.fps if self.a.fps else 0
            if self.clock - self.laugh_start >= dur:
                self.laugh_start = -1
                self.next_blink = self.clock + random.uniform(2.5, 5.0)

        self.update()

    # -- 合成当前帧
    def _compose(self):
        a = self.a
        if self.laugh_start >= 0:
            idx = int((self.clock - self.laugh_start) * a.fps)
            key = ("laugh", idx)
            if key != self.composite_key:
                self.composite = a.laugh(idx)
                self.composite_key = key
            return self.composite

        if a.has_pupil:
            dx = int(round(self.look_x * a.pupil_range))
            dy = int(round(self.look_y * a.pupil_range))
            dx2 = int(round(self.look_x * a.pupil_range2))
            dy2 = int(round(self.look_y * a.pupil_range2))
            bank = 1 if self.look_x > 0.5 else 0
            bf = int((self.clock - self.blink_start) * a.blink_fps) if self.blink_start >= 0 else -1
            key = ("eye", dx, dy, dx2, dy2, bank, bf)
            if key != self.composite_key:
                img = QImage(a.base)
                p = QPainter(img)
                if a.pupil2 is not None:
                    p.drawImage(dx2, dy2, a.pupil2)
                p.drawImage(dx, dy, a.pupil)
                if bf >= 0:
                    ov = a.blink(bank, bf)
                    if ov is not None:
                        p.drawImage(0, 0, ov)
                p.end()
                self.composite = img
                self.composite_key = key
            return self.composite

        # 没有眼球图层：走整帧 look
        idx = int(round((self.look_x + 1) * 0.5 * (a.eye_frames - 1)))
        key = ("look", idx)
        if key != self.composite_key:
            self.composite = a.look(idx)
            self.composite_key = key
        return self.composite

    # -- 与 Windows 版 Renderer.WarpBelly 完全一致的椭圆网格变形
    def _warp_belly(self, img, amount):
        if not HAS_NUMPY or abs(amount) < 1e-4:
            return img
        key = (int(amount * 256), int(self.poke_x), int(self.poke_y))
        hit = self._poke_cache.get(key)
        if hit is not None:
            return hit

        iw, ih = img.width(), img.height()
        fmt = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        ptr = fmt.constBits()
        ptr.setsize(fmt.sizeInBytes())
        src = np.frombuffer(bytes(ptr), dtype=np.uint8).reshape((ih, fmt.bytesPerLine() // 4, 4))[:, :iw]
        out = src.copy()

        k = iw / float(self.a.w)          # 素材尺寸与画布比例（正常就是 1）
        cx = self.poke_x * k
        cy = self.poke_y * k
        rx, ry = POKE_RX * k, POKE_RY * k
        top = max(int(POKE_TOP * k), int(cy - ry), 0)
        bottom = min(int(POKE_BOTTOM * k), int(cy + ry), ih - 2)
        left = max(0, int(cx - rx))
        right = min(iw - 2, int(cx + rx))
        if right <= left or bottom <= top:
            return img

        ys, xs = np.mgrid[top:bottom + 1, left:right + 1]
        dx = xs - cx
        dy = ys - cy
        r2 = dx * dx / (rx * rx) + dy * dy / (ry * ry)
        inside = r2 < 1.0
        neck = np.clip((ys - POKE_TOP * k) / (POKE_NECK * k), 0.0, 1.0)
        legs = np.clip((POKE_BOTTOM * k - ys) / (POKE_LEGS * k), 0.0, 1.0)
        fade = (neck * neck * (3 - 2 * neck)) * (legs * legs * (3 - 2 * legs))
        fall = np.where(inside, (1.0 - r2) ** 2 * amount * fade, 0.0)

        sx = np.clip(xs + dx * fall, 0, iw - 1.001)
        sy = np.clip(ys + dy * fall * 0.6, 0, ih - 1.001)
        ix = sx.astype(np.int32)
        iy = sy.astype(np.int32)
        fx = (sx - ix)[:, :, None]
        fy = (sy - iy)[:, :, None]
        a = src[iy, ix].astype(np.float32)
        b = src[iy, ix + 1].astype(np.float32)
        c = src[iy + 1, ix].astype(np.float32)
        d = src[iy + 1, ix + 1].astype(np.float32)
        samp = ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        samp = np.clip(samp, 0, 255).astype(np.uint8)
        mask = inside[:, :, None]
        out[top:bottom + 1, left:right + 1] = np.where(mask, samp, out[top:bottom + 1, left:right + 1])

        res = QImage(out.data, iw, ih, iw * 4, QImage.Format.Format_ARGB32_Premultiplied).copy()
        if len(self._poke_cache) > 48:
            self._poke_cache.clear()
        self._poke_cache[key] = res
        return res

    def paintEvent(self, e):
        img = self._compose()
        if img is None:
            return
        amt = self.poke_amount
        if self.poking:
            img = self._warp_belly(img, amt)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()

        # 与 Windows 版 Renderer.Render 相同的变换
        if self.moving:
            s = self.squash
            px = w * 0.5
            py = h * (0.62 if self.holding else 0.994)
            p.translate(px, py - (2 * self.scale if self.holding else 0))
            p.rotate(self.drag_angle)
            if self.holding:
                p.scale(1.008, 1.018)
            else:
                p.scale(1.0 + s, 1.0 - s)
            p.translate(-px, -py)

        p.drawImage(QRectF(0, 0, w, h), img, QRectF(0, 0, img.width(), img.height()))
        p.end()

    def closeEvent(self, e):
        self._save_pos()
        e.accept()


# ---------------------------------------------------------------- 单实例 & 启动
def notify_running(mode):
    sock = QLocalSocket()
    sock.connectToServer(LOCAL_SERVER)
    if sock.waitForConnected(300):
        sock.write((mode or "show").encode("utf-8"))
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def app_dirs():
    """素材查找目录：脚本目录 / 上一级目录 / 当前目录；打成单文件时还包括可执行文件所在目录。"""
    dirs = []
    if getattr(sys, "frozen", False):
        dirs.append(os.path.dirname(os.path.abspath(sys.executable)))
    here = os.path.dirname(os.path.abspath(__file__))
    dirs += [here, os.path.dirname(here), os.getcwd()]
    return dirs


def pick_assets(arg):
    cands = []
    if arg:
        cands.append(arg)
    for d in app_dirs():
        for fn in ("素材.nwp", "assets.nwp"):      # assets.nwp 是给 GitHub Release 用的 ASCII 别名
            cands.append(os.path.join(d, fn))
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def main():
    argv = sys.argv[1:]
    assets_arg = None
    if "--assets" in argv:
        i = argv.index("--assets")
        if i + 1 < len(argv):
            assets_arg = argv[i + 1]

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)

    if "--quit" in argv:
        if notify_running("quit"):
            print("已通知正在运行的小黄退出")
        sys.exit(0)

    if notify_running("laugh" if "--laugh" in argv else "show"):
        sys.exit(0)

    path = pick_assets(assets_arg)
    if not path:
        print("找不到 素材.nwp，请把它和本脚本放在同一目录（或用 --assets 指定路径）",
              file=sys.stderr)
        sys.exit(2)

    assets = Assets(path)
    pet = Pet(assets, app)
    pet.show()

    server = QLocalServer()

    def on_new():
        while server.hasPendingConnections():
            c = server.nextPendingConnection()
            c.waitForReadyRead(200)
            msg = bytes(c.readAll()).decode("utf-8", "ignore").strip()
            if msg == "quit":
                pet.quit()
            elif msg == "laugh":
                pet.start_laugh()
            else:
                pet.show()
                pet.raise_()
            c.disconnectFromServer()

    server.newConnection.connect(on_new)
    QLocalServer.removeServer(LOCAL_SERVER)
    server.listen(LOCAL_SERVER)

    if "--laugh" in argv:
        QTimer.singleShot(300, pet.start_laugh)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
