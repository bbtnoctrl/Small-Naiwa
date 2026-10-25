# 小黄桌宠 · Linux 版

和 Windows 版是同一只小黄、同一份素材（`素材.nwp`），只是把外壳换成了 Python + PyQt6。

## 依赖

- Python 3.9+
- PyQt6

```bash
# 方式一：pip
python3 -m pip install PyQt6

# 方式二：发行版软件包（Debian / Ubuntu / 麒麟等）
sudo apt install python3-pyqt6
```

## 运行

```bash
./run.sh
# 或者
python3 小黄桌宠.py
```

脚本会在**自身目录**和**上一级目录**里找 `素材.nwp`，所以把 `Linux版/` 放在仓库里直接就能跑；
也可以把 `素材.nwp` 拷进 `Linux版/`，或者用 `--assets` 指定路径：

```bash
python3 小黄桌宠.py --assets /path/to/素材.nwp
```

## 交互

| 操作 | 效果 |
| --- | --- |
| 待机 | 每 4~8 秒眨一次眼 |
| 鼠标移动 | 眼球跟着鼠标方向转（大眼 ±3px、小眼 ±1px） |
| 单击肚子 | 身体压一下再弹回 |
| 双击 | 啄肚肚：低头 → 趴着 → 抬头 → 站好，约 9 秒 |
| 左键拖动 | 移动位置，快速拖动时轻微倾斜，松手记住位置 |
| 右键 | 菜单：啄肚肚 / 停止 / 大小三档 / 置顶 / 全屏隐藏 / 回右下角 / 帮助 / 退出 |
| 托盘图标 | 单击弹菜单，双击回到屏幕右下角 |

命令行参数：

```bash
./run.sh --laugh    # 启动后立刻啄肚肚（也可以对已在运行的实例发送，效果相当于双击）
./run.sh --quit     # 让已运行的实例退出
```

多次运行不会出现多只小黄：第二次启动会把命令转给已在运行的实例然后退出。

## 设置保存位置

```
~/.config/XiaoHuangPet/settings.ini
```

里面记着位置、大小、置顶和全屏隐藏开关。删掉就恢复默认。

## 开机自启（GNOME / KDE 通用）

把 `小黄桌宠.desktop` 放到 `~/.config/autostart/`：

```ini
[Desktop Entry]
Type=Application
Name=小黄桌宠
Exec=/绝对路径/Linux版/run.sh
Icon=/绝对路径/形象/形象_245x312.png
Terminal=false
X-GNOME-Autostart-enabled=true
```

## X11 与 Wayland 的差别（重要）

| 功能 | X11 | Wayland |
| --- | --- | --- |
| 透明 + 无边框窗口 | ✅ | ✅ |
| 置顶 | ✅ | ⚠️ 部分合成器会忽略 |
| 记住/恢复窗口位置 | ✅ | ⚠️ 合成器通常不允许程序自己摆位置 |
| 眼球跟随鼠标 | ✅ 全局都能跟 | ⚠️ 出于安全，Wayland 只允许知道“鼠标在窗口内”，窗口外的位置拿不到，所以眼球只会在鼠标靠近时轻微动 |
| 托盘菜单 | ✅ | ✅（GNOME 需要 AppIndicator 扩展） |

**想要完整体验（尤其是眼球跟随），登录时选择 X11 会话**，或者给脚本强制走 XWayland：

```bash
QT_QPA_PLATFORM=xcb ./run.sh
```

## 和 Windows 版的差异

- 戳肚子：Windows 版是局部网格变形；Linux 版简化为整只小黄压一下再弹回（效果接近，代码简单）；
- 全屏自动隐藏：Linux 版暂未实现（需要读合成器状态），菜单里的开关先留着；
- 其他（眨眼、眼球图层 `pupil`/`pupil2`、啄肚肚序列、大小/置顶/托盘）与 Windows 版一致，读的是同一份 `metadata.json`。

## 排错

| 现象 | 原因 / 处理 |
| --- | --- |
| 提示找不到 `素材.nwp` | 把素材包放到脚本同目录或上一级目录，或用 `--assets` |
| 窗口是黑底方块 | 没开合成器（compositor）。KDE/GNOME 默认开启；i3/openbox 需要装 `picom` 并启动 |
| 双卡/远程桌面下很卡 | 试试 `QT_QPA_PLATFORM=xcb`，或 `QSG_RENDER_LOOP=basic` |
| 右键没反应、托盘没图标 | Wayland + 没有 AppIndicator 扩展；菜单仍可用窗口内右键 |
