# 小黄桌宠 · XiaoHuang Desktop Pet

一只会跟着鼠标转眼睛、会眨眼、被戳肚子会凹下去再弹回来、双击会低头啄肚肚的桌面宠物。

**Windows 与 Linux 双平台**：Windows 是单文件 exe，Linux 是 Python + PyQt6 版，两者读**同一份素材包 `素材.nwp`**，动效参数一致。

![待机](形象/形象_245x312.png)

---

## 快速开始

### Linux：不用开终端，双击就能跑

1. 到 **[Releases](https://github.com/bbtnoctrl/Small-Naiwa/releases/latest)** 下载 **`xiaohuang-linux-x86_64.tar.gz`**（约 100 MB）
2. 右键压缩包 →「**解压到此处**」
3. 双击解压出来的 **`xiaohuang.AppImage`** —— 小黄就出来了

> 压缩包会把可执行权限一起解出来，所以**不需要 `chmod`、不需要终端**。
> 若双击没反应（部分文件管理器默认不执行）：右键 AppImage →「属性」→「权限」→ 勾选「**允许作为程序执行**」，再双击。

**如果愿意用一次终端**（同样简单）：

```bash
chmod +x xiaohuang-x86_64.AppImage && ./xiaohuang-x86_64.AppImage
```

**AppImage 提示 FUSE 错误**（容器/精简系统）：

```bash
./xiaohuang.AppImage --appimage-extract-and-run
```

### Windows：也是双击

到仓库首页或 Releases 下载 `小黄桌宠.exe` + `素材.nwp`，**放在同一个文件夹**，双击 exe。
需要 .NET Framework 4.x（Win10/11 自带）。

首次运行若被 Windows 拦截（exe 无数字签名），点「更多信息 → 仍要运行」，或在 ZIP 属性里勾选「解除锁定」后再解压。

### 从源码运行（给要改代码的人）

```bash
git clone https://github.com/bbtnoctrl/Small-Naiwa.git
cd Small-Naiwa/Linux版
./run.sh          # 依赖自动安装（约 40 MB，只装一次）
```

Windows 上也能跑同一份 Python 代码：

```powershell
C:\Users\Administrator\miniconda3\envs\torch\python.exe "路径\Linux版\小黄桌宠.py"
```

**依赖自动安装**：第一次运行若系统缺 PyQt6，会自己在 `~/.local/share/xiaohuang/venv` 建独立环境安装（约 40 MB，只装一次，不动系统 Python）。

想让它出现在应用菜单、双击就能开：

```bash
./install.sh                # 装进应用菜单
./install.sh --autostart    # 顺便开机自启
```

也可以先手动装依赖：`sudo apt install python3-pyqt6 python3-numpy`。

脚本会自动在自身目录和上一级目录里找 `素材.nwp`；也可以用 `python3 小黄桌宠.py --assets /路径/素材.nwp` 指定。

Linux 版的完整说明（一键安装、X11/Wayland 差异、打包成单文件二进制、排错）见 [`Linux版/README.md`](Linux版/README.md)。

---

## 新增：Linux 系统适配

Linux 版是**本项目独立实现的一套桌宠外壳**，不是把 exe 塞进 Wine：

| | 实现 |
| --- | --- |
| 语言 / 框架 | Python 3 + PyQt6（无边框半透明窗口） |
| 素材 | 直接读同一个 `素材.nwp`（普通 ZIP + PNG），不需要重新制作 |
| 动效算法 | 与 Windows 版相同：`PokeAmount` 衰减振荡公式、`WarpBelly` 逐像素椭圆网格变形、落地 `Squash`、拖动弹簧 |
| 数值验证 | 把 Windows 的 `Renderer.WarpBelly` 原码抽出来编译成 `源码/tools/WarpCheck.cs`，与 Python 移植版跑同一张图逐像素比对：**最大差 1/255，差值>2 的像素 0 个** |
| 依赖 | PyQt6（必需）、numpy（用于戳肚子变形，缺失时退化为不变形） |

---

## 和 Windows 版的区别

### 动效：一致

眨眼（7 帧 / 4~8 秒）、眼球跟随（大眼 ±3px、小眼 ±1px）、啄肚肚（280 帧 @30fps）、戳肚子回弹、按住压扁、落地弹跳、拖动倾斜 —— 参数和公式取自 Windows 版，是同一套。

### 环境：有差异

| 项目 | Windows | Linux |
| --- | --- | --- |
| 眼球跟随鼠标 | 全局任意位置 | **X11 全局**；Wayland 下系统不提供全局鼠标位置，只有鼠标进入窗口时才跟随 |
| 窗口定位 | 程序自己摆 | X11 可以；Wayland 由合成器决定，可能忽略程序设定的位置 |
| 全屏自动隐藏 | 读前台窗口状态 | 依赖 `xdotool`（`sudo apt install xdotool`），没装则自动关闭 |
| 托盘菜单 | 原生托盘 | GNOME 需要 AppIndicator 扩展；KDE 正常。窗口内右键始终可用 |
| 大小档位 | 百分比缩放 | 0.75 / 1.0 / 1.25 三档 |
| 运行方式 | 单文件 exe，双击即用 | 需要 Python 环境，`./run.sh` 启动 |
| 设置保存 | `%LOCALAPPDATA%\XiaoHuangPet\settings.ini` | `~/.config/XiaoHuangPet/settings.ini` |

---

## 功能

| 操作 | 效果 |
| --- | --- |
| 待机 | 视频第 16 帧形象，每 4~8 秒自然眨眼（整只眼睛纵向压扁成细缝） |
| 鼠标靠近 | 眼球在眼眶里朝鼠标方向转动，大眼与小眼各自独立位移 |
| 单击肚子 | 肚子局部凹陷 → 回弹 → 轻微振荡，约 1 秒；点其他部位无效 |
| 双击 | **啄肚肚**：低头弯下去 → 趴着 → 倒放抬头 → 站好，约 9.3 秒 |
| 拖动 | 随移动方向倾斜，松手落地弹跳，记住位置，支持多显示器 |
| 全屏应用 | Windows 自动隐藏／Linux(X11 + xdotool) 自动隐藏 |
| 右键 / 托盘 | 啄肚肚、停止、大小三档、置顶、全屏隐藏、回到右下角、使用说明、退出 |

重复启动不会出现两只小黄：第二次启动会把命令转给已运行的实例。

---

## 文件结构

```
小黄桌宠.exe              Windows 成品（单文件，137 KB）
素材.nwp                  形象素材包（普通 ZIP，15 MB）
使用说明.txt              Windows 版操作说明
README.md                 本文件
LICENSE                   MIT（本仓库原创部分，见 NOTICE.md）
NOTICE.md                 第三方署名与声明
源码/                     Windows 版 C# 源码
  Naiwa.cs                全部逻辑：Motion 状态机 / Assets 素材 / PetForm 窗口
  AssemblyInfo.cs         程序集信息
  build.cmd               一键编译（调用系统自带 csc.exe）
  pet.ico / Pet.manifest  图标与 DPI 声明
  tools/
    make_assets_3d.py     素材生成脚本（眼窝 + 眼球贴片 + 眨眼 + 啄肚肚序列）
    make_assets_3d_plain.py  备用：不做眼球合成，直接用视频原图
    WarpCheck.cs          戳肚子变形的一致性比对工具
Linux版/                  Linux 版（Python + PyQt6，本项目独立实现）
  小黄桌宠.py             主程序
  run.sh                  启动脚本
  requirements.txt        依赖：PyQt6、numpy
  README.md               Linux 使用说明
形象/                     形象图与预览
预览/                     交互演示 mp4 / gif
```

---

## 从源码编译（Windows）

```bat
cd 源码
build.cmd
```

直接调用系统自带的 `csc.exe`，不需要 Visual Studio。

---

## 素材包协议

`素材.nwp` 就是个 ZIP，程序用 `ZipFile.OpenRead`（Linux 版用 `zipfile`）读取：

```
metadata.json          width height frames fps eyeFrames blinkFrames blinkFps
                       + pupilRange pupilRange2 eyeX eyeY（眼球可动时需要）
look/00.png 01.png     整帧待机（没有眼球图层时走这条路径）
base/00.png            眼窝底板：整帧，但眼球位置被填成单一绿色
pupil/00.png           大眼眼球贴片（视频原像素，圆形裁切，带自带高光）
pupil2/00.png          小眼眼球贴片（贴着脸型边缘，位移更小）
blink/0/00..06.png     眨眼帧：整帧，整只眼睛纵向压扁 1.0→0.55→0.22→0.06→回弹
blink/1/...            第二组，按视线方向选用
laugh/0000..0279.png   啄肚肚序列：正放 190 帧 + 倒放 84 帧 + 6 帧渐变回待机
```

所有帧必须严格等于 `width × height`，PNG + 透明底；单边 ≤1024px、帧数 ≤2000、fps 1~120。

---

## 素材是怎么做出来的

1. 3D 渲染视频逐帧抠像（灰色影棚背景）→ 480×428 透明 PNG，30fps；
2. 取第 16 帧为基准，缩放到 241×262 后贴进 245×312 画布；
3. 自动定位两只瞳孔 → 眼窝填成单一绿色、眼球裁成圆形贴片（保留渲染自带的高光）；
4. 眨眼帧：用脸颊肤色盖住眼睛，再把整只眼睛纵向压扁；
5. 啄肚肚：正放 190 帧 → 从与末帧姿态一致的帧开始倒放（抬头）→ 末 6 帧渐变到待机图，消除切回待机时的闪烁；
6. 打包为 `素材.nwp`。

---

## 代码归属

| 部分 | 来源 |
| --- | --- |
| **Linux 版**（`Linux版/` 全部 Python 代码） | **本项目原创实现**，MIT |
| 形象素材、`素材.nwp`、素材生成脚本、文档 | **本项目原创**，MIT |
| Windows 版程序主体（`源码/Naiwa.cs` 的 Motion / Renderer / PetForm） | 基于 [yugh6](https://github.com/yugh6) 的「奶蛙桌宠」修改，署名与声明见 [NOTICE.md](NOTICE.md) |

- 本项目**不包含**原奶蛙桌宠的任何形象素材、音效或二进制文件；
- 原作者声明：分享请注明作者及原项目地址，禁止搬运冒充原创；
- 除上述第三方基础代码外，本仓库其余内容均为原创，按根目录 `LICENSE`（MIT）授权。
