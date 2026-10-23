"""小黄桌宠：从一张白底原图生成全部素材、打包 素材.nwp 并编译 exe。

用法：python make_assets.py
依赖：Pillow、numpy，以及本机 .NET Framework 4 的 csc.exe

素材包结构（素材.nwp 就是 zip）：
    metadata.json      width height frames fps eyeFrames blinkFrames blinkFps
                       pupilRange eyeX eyeY  (可选，有 base/ + pupil/ 时生效)
    look/00 01.png     整帧：插座 + 眼球，用于托盘图标和过渡帧
    base/00.png        只有眼白（插座），没有眼球
    pupil/00.png       只有两只眼球，透明底，位置=中立位
    blink/b/00..06.png 眼皮，透明底，叠在 base+pupil 上面
    laugh/0000..0059   整帧大笑序列，最后一帧是"笑瘫"姿势
"""
import json, math, os, shutil, subprocess, zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = r"C:\Users\Administrator\.dsh\attachments\v1\objects\9b\9b8d448183a174cdc9d77da10fc1a3fe44676664e8fd8ea0a00070f2361f8839"
PROJ = r"D:\BrowserDownload\小黄桌宠"
WORK = r"C:\Users\Administrator\Documents\deepseek-harness\default-workspace\pet-new\work"
CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
NAME = "小黄"
EXE = os.path.join(PROJ, NAME + "桌宠.exe")

CW, CH = 245, 312
FOOT = CH - 8
CONTENT_W = 205
LAUGH_FPS, NL = 15, 60
PUPIL_RANGE = 4
os.makedirs(WORK, exist_ok=True)


def flood_from_border(mask):
    cur = np.zeros_like(mask)
    cur[0, :] = mask[0, :]; cur[-1, :] = mask[-1, :]
    cur[:, 0] |= mask[:, 0]; cur[:, -1] |= mask[:, -1]
    while True:
        d = cur.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            d |= np.roll(np.roll(cur, dy, 0), dx, 1)
        d &= mask
        if np.array_equal(d, cur):
            return cur
        cur = d


def flood_from(seeds, blocked):
    """grow `seeds` through everything except `blocked`."""
    cur = seeds & ~blocked
    while True:
        d = cur.copy()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            d |= np.roll(np.roll(cur, dy, 0), dx, 1)
        d &= ~blocked
        if np.array_equal(d, cur):
            return cur
        cur = d


def gblur(a, r):
    a8 = np.clip(a, 0, 255).astype(np.uint8)
    if a8.ndim == 2:
        return np.asarray(Image.fromarray(a8, "L").filter(ImageFilter.GaussianBlur(r)), dtype=np.float32)
    return np.dstack([gblur(a8[:, :, i], r) for i in range(a8.shape[2])])


# 1 cutout -----------------------------------------------------------------
im = Image.open(SRC).convert("RGB")
arr = np.asarray(im).astype(np.int16)
H, W = arr.shape[:2]
mx = arr.max(axis=2); mn = arr.min(axis=2)
sat = (mx - mn) * 255.0 / np.maximum(mx, 1)
lum = arr.mean(axis=2)

bg_like = (sat < 28) & (mn > 55)
outside = flood_from_border(bg_like)
alpha = np.where(outside, 0, 255).astype(np.float32)

probe = Image.fromarray(np.dstack([arr.clip(0, 255).astype(np.uint8), alpha.astype(np.uint8)]), "RGBA").getbbox()
region = np.arange(H)[:, None] >= probe[3] - 105
shadowish = (sat < 115) | ((lum > 150) & (sat < 135))
alpha = np.where(region & shadowish, 0, alpha)
foot_rows = np.where((alpha > 0) & (sat > 145))[0]
if len(foot_rows):
    alpha[foot_rows.max() + 1:, :] = 0
alpha = np.clip(alpha, 0, 255).astype(np.uint8)
alpha[alpha < 40] = 0
full = Image.fromarray(np.dstack([arr.clip(0, 255).astype(np.uint8), alpha]), "RGBA")
bbox = full.getbbox()

# 2 canvas -----------------------------------------------------------------
cw, ch = bbox[2] - bbox[0], bbox[3] - bbox[1]
s = min(CONTENT_W / cw, (FOOT - 6.0) / ch)
nw, nh = int(round(cw * s)), int(round(ch * s))
src = np.asarray(full.crop(bbox)).astype(np.float32)
aa = src[:, :, 3:4] / 255.0
prem = np.concatenate([src[:, :, :3] * aa, src[:, :, 3:4]], axis=2)
chans = [Image.fromarray(prem[:, :, i], "F").resize((nw, nh), Image.LANCZOS) for i in range(4)]
small = np.dstack([np.asarray(c, dtype=np.float32) for c in chans])
al = small[:, :, 3:4] / 255.0
col = np.where(al > 1e-3, small[:, :, :3] / np.maximum(al, 1e-3), 0).clip(0, 255)
piece = np.dstack([col, small[:, :, 3:4].clip(0, 255)]).astype(np.uint8)
piece[piece[:, :, 3] < 40] = 0

canvas = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
ox, oy = (CW - nw) // 2, FOOT - nh
canvas.paste(Image.fromarray(piece, "RGBA"), (ox, oy))

ca0 = np.asarray(canvas).astype(np.int16)
a0 = ca0[:, :, 3]
r0 = ca0[:, :, :3]
s0 = (r0.max(axis=2) - r0.min(axis=2)) * 255.0 / np.maximum(r0.max(axis=2), 1)
l0 = r0.mean(axis=2)
rows = np.arange(CH)[:, None] >= (np.where(a0 > 8)[0].max() - 60)
ca0[:, :, 3] = np.where(rows & (a0 > 0) & (s0 < 70) & (l0 > 200), 0, a0)
canvas = Image.fromarray(ca0.clip(0, 255).astype(np.uint8), "RGBA")
canvas.save(os.path.join(WORK, "20_base.png"))

ca = np.asarray(canvas)
ys, xs = np.where(ca[:, :, 3] > 8)
box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
bw, bh = box[2] - box[0] + 1, box[3] - box[1] + 1

# 3 eyes + mouth -----------------------------------------------------------
rgb = ca[:, :, :3].astype(np.int16)
lums = rgb.mean(axis=2)
dark = (lums < 95) & (ca[:, :, 3] > 200)
bb = np.zeros_like(dark); bb[box[1] + 22:box[1] + 73, :] = True
dark &= bb
mid = (box[0] + box[2]) // 2
eyes = []
for x0, x1 in ((0, mid), (mid, CW)):
    yy, xx = np.where(dark[:, x0:x1])
    if len(yy) < 40:
        raise SystemExit("eye detection failed")
    xl, xr = float(xx.min() + x0), float(xx.max() + x0)
    yt, yb = float(yy.min()), float(yy.max())
    eyes.append({"cx": (xl + xr) / 2, "cy": (yt + yb) / 2, "r": max(xr - xl, yb - yt) / 2})
print("eyes", json.dumps(eyes))

mb = np.zeros(CH, bool); mb[box[1] + int(0.30 * bh):box[1] + int(0.45 * bh)] = True
cand = (lums < 118) & mb[:, None] & (ca[:, :, 3] > 200)
yy, xx = np.where(cand)
mouth_y = int(np.percentile(yy, 60)); mouth_x = int(xx.mean())
mouth_px = tuple(int(v) for v in np.median(rgb[cand], axis=0))
print("mouth", mouth_px, "x", mouth_x, "y", mouth_y)

yy2, xx2 = np.mgrid[0:CH, 0:CW]

# 4 eyeball sprite, empty socket, and the eyelid skin ----------------------
pupil_mask = np.zeros((CH, CW), bool)
ring_cols = []
for e in eyes:
    rr = e["r"] + 4.0
    d2 = (xx2 - e["cx"]) ** 2 + (yy2 - e["cy"]) ** 2
    disk = d2 <= rr * rr
    m = disk & (lums < 112)
    border = disk & (d2 >= (rr - 1.6) ** 2) & ~m
    reachable = flood_from(border, m)
    blob = disk & ~reachable
    pupil_mask |= blob
    ann = (d2 > (e["r"] + 1.5) ** 2) & (d2 <= (e["r"] + 3.8) ** 2) & ~m & (ca[:, :, 3] > 200)
    if ann.sum() > 20:
        ring_cols.append(np.median(rgb[ann], axis=0))
ring_col = np.median(np.array(ring_cols), axis=0)

pa = gblur(pupil_mask.astype(np.float32) * 255.0, 0.9)
pupil_img = Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), pa.clip(0, 255).astype(np.uint8)]), "RGBA")

socket = canvas.copy()
sd = ImageDraw.Draw(socket)
for e in eyes:
    R = e["r"] + 0.5
    box_e = (e["cx"] - R, e["cy"] - R, e["cx"] + R, e["cy"] + R)
    ss = 4
    m4 = Image.new("L", (int(2 * R * ss) + 2, int(2 * R * ss) + 2), 0)
    ImageDraw.Draw(m4).ellipse((0, 0, m4.size[0] - 1, m4.size[1] - 1), fill=255)
    m4 = m4.resize((int(2 * R) + 1, int(2 * R) + 1), Image.LANCZOS)
    socket.paste(Image.new("RGBA", m4.size, tuple(int(v) for v in ring_col) + (255,)),
                 (int(box_e[0]), int(box_e[1])), m4)

# skin for the eyelid, taken from the eye-free body
m = np.zeros((CH, CW), bool)
for e in eyes:
    m |= ((xx2 - e["cx"]) ** 2 + (yy2 - e["cy"]) ** 2) <= (e["r"] + 3.5) ** 2
f = ca.astype(np.float32)
for _ in range(80):
    acc = np.zeros_like(f); cnt = np.zeros((CH, CW, 1), np.float32)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        acc += np.roll(np.roll(f, dy, 0), dx, 1); cnt += 1
    f = np.where(m[:, :, None], acc / cnt, f)
skin = Image.fromarray(np.dstack([f[:, :, :3].astype(np.uint8), ca[:, :, 3]]), "RGBA")
skin.save(os.path.join(WORK, "21_skin.png"))
socket.save(os.path.join(WORK, "22_socket.png"))
pupil_img.save(os.path.join(WORK, "23_pupil.png"))


def lid_mask(c):
    """eyelid flap: covers the top of both eyes, c=0 open, 1 shut (a sliver stays dark)."""
    out = np.zeros((CH, CW), bool)
    for e in eyes:
        rr = e["r"]
        R = rr + 5.5
        dx = xx2 - e["cx"]; dy = yy2 - e["cy"]
        cover = -rr + 1.84 * rr * c + 2.2 * (dx / rr) ** 2
        out |= (dx * dx + dy * dy <= (R + 1) ** 2) & (dy < cover)
    return out


def flap(c):
    am = gblur(lid_mask(c).astype(np.float32) * 255.0, 0.9)
    img = skin.copy()
    img.putalpha(Image.fromarray(am.clip(0, 255).astype(np.uint8), "L"))
    return img


def mouth_mask(w, h):
    W_, H_ = max(3, int(round(w))), max(2, int(round(2 * h)))
    mm = Image.new("L", (W_, H_), 0)
    ImageDraw.Draw(mm).ellipse((0, 0, W_ - 1, H_ - 1), fill=255)
    a_ = np.asarray(mm).copy(); a_[:H_ // 2, :] = 0
    return Image.fromarray(a_, "L")


def frame(dx=0, dy=0, lid=0.0, mouth=0.0):
    img = socket.copy()
    img.alpha_composite(pupil_img, (int(round(dx)), int(round(dy))))
    if lid > 0.001:
        img.alpha_composite(flap(lid))
    if mouth > 0.01:
        w = 9 + 25 * mouth
        h = 3 + 13 * mouth
        mk = mouth_mask(w, h)
        img.paste(Image.new("RGBA", mk.size, mouth_px + (255,)),
                  (int(mouth_x - mk.size[0] / 2), int(mouth_y - 3)), mk)
    return img


def affine(img, sx, sy, rot, ty):
    th = math.radians(rot); c, s_ = math.cos(th), math.sin(th)
    cx, by = CW / 2, float(FOOT)
    a = c / sx; b = s_ / sx; d_ = -s_ / sy; e = c / sy
    return img.transform((CW, CH), Image.AFFINE,
                         (a, b, cx - a * cx - b * (by + ty), d_, e, by - d_ * cx - e * (by + ty)),
                         Image.BICUBIC)


# 5 frames -----------------------------------------------------------------
looks = [frame(0, 0), frame(PUPIL_RANGE * 0.9, 0)]
CLOSE = (0.0, 0.32, 0.66, 0.92, 0.60, 0.26, 0.0)
blinks = [[frame(0, 0, lid=c) for c in CLOSE] for _ in range(2)]

laugh = []
SETTLE = dict(sy=0.93, sx=1.04, rot=2.2, mouth=0.06, lid=0.72)
for i in range(NL):
    t = i / (NL - 1)
    beat = abs(math.sin(math.pi * t * 7.0))
    sy = 1.0 - 0.05 * beat
    sx = 1.0 + 0.35 * (1.0 - sy)
    ty = -7.0 * beat
    rot = 1.8 * math.sin(2 * math.pi * t * 3.0)
    lid = 0.62 - 0.10 * beat
    mouth = 0.34 + 0.66 * beat
    if t > 0.78:
        u = min(1.0, (t - 0.78) / 0.22); u = u * u * (3 - 2 * u)
        sy = sy * (1 - u) + SETTLE["sy"] * u
        sx = sx * (1 - u) + SETTLE["sx"] * u
        ty = ty * (1 - u)
        rot = rot * (1 - u) + SETTLE["rot"] * u
        lid = lid * (1 - u) + SETTLE["lid"] * u
        mouth = mouth * (1 - u) + SETTLE["mouth"] * u
    laugh.append(affine(frame(lid=lid, mouth=mouth), sx, sy, rot, ty))

# 6 pack -------------------------------------------------------------------
dst = os.path.join(PROJ, "素材源")
shutil.rmtree(dst, ignore_errors=True)


def save(img, rel):
    p = os.path.join(dst, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p, "PNG")


save(socket, "base/00.png")
save(pupil_img, "pupil/00.png")
for i, img in enumerate(looks):
    save(img, "look/%02d.png" % i)
for bank in range(2):
    for k, img in enumerate(blinks[bank]):
        save(img, "blink/%d/%02d.png" % (bank, k))
for i, img in enumerate(laugh):
    save(img, "laugh/%04d.png" % i)

meta = {"width": CW, "height": CH, "frames": NL, "fps": LAUGH_FPS,
        "eyeFrames": len(looks), "blinkFrames": len(blinks[0]), "blinkFps": 30,
        "pupilRange": PUPIL_RANGE,
        "eyeX": round(sum(e["cx"] for e in eyes) / 2, 1),
        "eyeY": round(sum(e["cy"] for e in eyes) / 2, 1)}
json.dump(meta, open(os.path.join(dst, "metadata.json"), "w"), indent=1)

nwp = os.path.join(PROJ, "素材.nwp")
with zipfile.ZipFile(nwp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, _, files in os.walk(dst):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            z.write(p, os.path.relpath(p, dst).replace("\\", "/"))
print("nwp MB", round(os.path.getsize(nwp) / 1e6, 2), meta)

imgd = os.path.join(PROJ, "形象")
os.makedirs(imgd, exist_ok=True)
full.crop(bbox).save(os.path.join(imgd, "原图去底.png"))
looks[0].save(os.path.join(imgd, "形象_245x312.png"))
pair = Image.new("RGBA", (245 * 2 + 30, 312), (255, 255, 255, 255))
pair.alpha_composite(looks[0], (0, 0)); pair.alpha_composite(looks[1], (275, 0))
pair.resize((pair.width * 2, pair.height * 2), Image.LANCZOS).save(os.path.join(imgd, "预览_待机与转眼.png"))

# 7 build ------------------------------------------------------------------
cmd = [CSC, "/nologo", "/target:winexe", "/optimize+", "/platform:anycpu",
       "/win32icon:pet.ico", "/win32manifest:Pet.manifest", "/out:" + EXE,
       "/reference:System.Drawing.dll", "/reference:System.Windows.Forms.dll",
       "/reference:System.IO.Compression.dll", "/reference:System.IO.Compression.FileSystem.dll",
       "/reference:System.Web.Extensions.dll", "Naiwa.cs", "AssemblyInfo.cs"]
res = subprocess.run(cmd, cwd=os.path.join(PROJ, "源码"), capture_output=True, text=True, errors="replace")
print("csc rc", res.returncode, res.stdout[-800:], res.stderr[-800:])
print("done", os.path.getsize(EXE) if os.path.exists(EXE) else "MISSING")
