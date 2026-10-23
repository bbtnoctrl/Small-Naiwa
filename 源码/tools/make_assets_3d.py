"""小黄桌宠 · 3D 形象素材：眼窝 + 黑眼球 + 眨眼帧（从视频第 16 帧重建）。

只重写 base/ pupil/ pupil2/ look/ blink/ 和 metadata.json，laugh/ 保持不动。
"""
import os, json, zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = r"D:\BrowserDownload\小黄戳肚肚\帧"
PROJ = r"D:\BrowserDownload\小黄桌宠"
ASSETS = os.path.join(PROJ, "素材源")
WORK = r"C:\Users\Administrator\Documents\deepseek-harness\default-workspace\pet-new\work"
IDLE = 16
CROP = (52, 2, 443, 427)
OUTWH = (241, 262)
PASTE = (2, 42)
CW, CH = 245, 312
RANGE_BIG, RANGE_SMALL = 3, 1

f = Image.open(os.path.join(SRC, "%04d.png" % IDLE)).convert("RGBA")
a = np.asarray(f).astype(np.int16)
rgb = a[:, :, :3]; alpha = a[:, :, 3]
lum = rgb.mean(axis=2)
H, W = lum.shape
yy, xx = np.mgrid[0:H, 0:W]


def blur(a_, r):
    a8 = np.clip(a_, 0, 255).astype(np.uint8)
    if a8.ndim == 2:
        return np.asarray(Image.fromarray(a8, "L").filter(ImageFilter.GaussianBlur(r)), np.float32)
    return np.dstack([blur(a8[:, :, i], r) for i in range(a8.shape[2])])


def components(mask, min_area):
    seen = np.zeros_like(mask); out = []
    idx = np.argwhere(mask & ~seen)
    while len(idx):
        y0, x0 = idx[0]
        cur = np.zeros_like(mask); cur[y0, x0] = True
        while True:
            d = cur.copy()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                d |= np.roll(np.roll(cur, dy, 0), dx, 1)
            d &= mask
            if np.array_equal(d, cur):
                break
            cur = d
        seen |= cur
        if int(cur.sum()) >= min_area:
            out.append(cur)
        idx = np.argwhere(mask & ~seen)
    return out


# 1. the two eyeballs -------------------------------------------------------
dark = (lum < 85) & (alpha > 128)
dark[180:, :] = False
eyes = []
for c in components(dark, 350):
    ys, xs = np.where(c)
    if xs.mean() > 260:
        continue
    eyes.append({"cx": float(xs.mean()), "cy": float(ys.mean()),
                 "r": float(np.sqrt(len(ys) / np.pi))})
eyes.sort(key=lambda e: -e["r"])
big = eyes[0]
print("eyes", [(round(e["cx"], 1), round(e["cy"], 1), round(e["r"], 1)) for e in eyes])

# 2. green sockets ----------------------------------------------------------
socket_rgb = rgb.astype(np.float32).copy()
for e in eyes:
    cx, cy, r = e["cx"], e["cy"], e["r"]
    dist_m = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    ring = (dist_m > r + 2.6) & (dist_m < r + 5.2) & (alpha > 200)
    green = np.median(rgb[ring], axis=0) if int(ring.sum()) > 30 else np.array([170, 176, 60], np.float32)
    w = np.clip(((r + 5.0) - dist_m) / 1.2, 0, 1)[:, :, None]
    w = w * (alpha >= 250)[:, :, None]          # never repaint the silhouette edge
    socket_rgb = np.where((dist_m <= r + 5.0)[:, :, None],
                          socket_rgb * (1 - w) + green[None, None, :] * w, socket_rgb)
    # the pale specular between pupil and ring goes too, so the socket is one flat green
    sat_all = (rgb.max(axis=2) - rgb.min(axis=2)) * 255.0 / np.maximum(rgb.max(axis=2), 1)
    pale = (dist_m <= r + 2.9) & (sat_all < 85) & (lum > 140)
    socket_rgb = np.where(pale[:, :, None], green[None, None, :], socket_rgb)
socket_img = Image.fromarray(np.dstack([socket_rgb.clip(0, 255).astype(np.uint8),
                                        alpha.clip(0, 255).astype(np.uint8)]), "RGBA")

# 3. clean black pupils -----------------------------------------------------
dark_px = rgb[(lum < 70) & (alpha > 200)]
black = np.median(dark_px, axis=0) if len(dark_px) else np.array([8, 8, 10], np.float32)
patches = []
for e in eyes:
    R = int(round(e["r"] + 5))
    box = (int(e["cx"] - R), int(e["cy"] - R), int(e["cx"] + R), int(e["cy"] + R))
    piece = f.crop(box).convert("RGBA")
    ss = 4
    rr = (e["r"] + 2.6) * ss
    m4 = Image.new("L", (2 * int(rr) + 4, 2 * int(rr) + 4), 0)
    ImageDraw.Draw(m4).ellipse((0, 0, m4.size[0] - 1, m4.size[1] - 1), fill=255)
    msk = np.asarray(m4.resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)).astype(np.float32)
    sub = rgb[box[1]:box[3], box[0]:box[2]]
    face = (sub[:, :, 0] > sub[:, :, 1] + 8)
    msk = np.where(face, 0, msk)
    # never paint outside the body: the small eye sits right on the silhouette
    msk = msk * (alpha[box[1]:box[3], box[0]:box[2]] / 255.0)
    piece.putalpha(Image.fromarray(msk.clip(0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.6)))
    patches.append({"img": piece, "box": box})

# 4. face skin for blinking -------------------------------------------------
skin_rgb = rgb.astype(np.float32).copy()
for e in eyes:
    cx, cy, r = e["cx"], e["cy"], e["r"]
    R2 = r + 20.0
    cheek = np.zeros((H, W), bool)
    x1 = min(W, int(cx + 3.6 * r)); x0 = min(x1 - 2, int(cx + 1.6 * r))
    y0 = max(0, int(cy - 1.2 * r)); y1 = min(H, int(cy + 1.6 * r))
    cheek[y0:y1, x0:x1] = True
    cheek &= (alpha > 220)
    if int(cheek.sum()) < 40:
        cheek = (np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) > r + 10) & (alpha > 220)
    face_col = np.median(rgb[cheek], axis=0) if int(cheek.sum()) else np.array([232, 196, 92], np.float32)
    dist_m = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    t = np.clip((yy - (cy - R2)) / (2 * R2), 0, 1)[:, :, None]
    fill = face_col[None, None, :] * (1.03 - 0.08 * t)
    w = np.clip((R2 - dist_m) / max(1.0, R2 - (r + 8.0)), 0, 1)[:, :, None]
    skin_rgb = np.where((dist_m <= R2)[:, :, None], skin_rgb * (1 - w) + fill * w, skin_rgb)
skin = Image.fromarray(np.dstack([skin_rgb.clip(0, 255).astype(np.uint8),
                                  alpha.clip(0, 255).astype(np.uint8)]), "RGBA")

# 5. helpers ---------------------------------------------------------------
SX = OUTWH[0] / float(CROP[2] - CROP[0])
SY = OUTWH[1] / float(CROP[3] - CROP[1])


def to_canvas(img):
    src = np.asarray(img.crop(CROP)).astype(np.float32)
    al = src[:, :, 3:4] / 255.0
    prem = np.concatenate([src[:, :, :3] * al, src[:, :, 3:4]], axis=2)
    ch = [Image.fromarray(prem[:, :, i], "F").resize(OUTWH, Image.LANCZOS) for i in range(4)]
    sm = np.dstack([np.asarray(c, dtype=np.float32) for c in ch])
    a2 = sm[:, :, 3:4] / 255.0
    col = np.where(a2 > 1e-3, sm[:, :, :3] / np.maximum(a2, 1e-3), 0).clip(0, 255)
    piece = np.dstack([col, sm[:, :, 3:4].clip(0, 255)]).astype(np.uint8)
    piece[piece[:, :, 3] < 40] = 0
    out = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    out.paste(Image.fromarray(piece, "RGBA"), PASTE)
    return out


def sprite_on_canvas(p):
    x0 = (p["box"][0] - CROP[0]) * SX + PASTE[0]
    y0 = (p["box"][1] - CROP[1]) * SY + PASTE[1]
    w = (p["box"][2] - p["box"][0]) * SX
    h = (p["box"][3] - p["box"][1]) * SY
    arr = np.asarray(p["img"]).astype(np.float32)
    al = arr[:, :, 3:4] / 255.0
    prem = np.concatenate([arr[:, :, :3] * al, arr[:, :, 3:4]], axis=2)
    chans = [Image.fromarray(prem[:, :, k], "F").resize((max(1, int(round(w))), max(1, int(round(h)))), Image.LANCZOS)
             for k in range(4)]
    sm = np.dstack([np.asarray(c, np.float32) for c in chans])
    a2 = sm[:, :, 3:4] / 255.0
    col = np.where(a2 > 1e-3, sm[:, :, :3] / np.maximum(a2, 1e-3), 0).clip(0, 255)
    piece = np.dstack([col, sm[:, :, 3:4].clip(0, 255)]).astype(np.uint8)
    piece[piece[:, :, 3] < 40] = 0
    out = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    out.paste(Image.fromarray(piece, "RGBA"), (int(round(x0)), int(round(y0))))
    return out


def compose(ox, oy):
    img = socket_img.copy()
    for p in patches:
        img.alpha_composite(p["img"], (p["box"][0] + ox, p["box"][1] + oy))
    return img


def blink_frame(q):
    img = skin.copy()
    for e in eyes:
        cx, cy, r = e["cx"], e["cy"], e["r"]
        R = int(round(r + 6))
        box = (int(cx - R), int(cy - R), int(cx + R), int(cy + R))
        eye_p = f.crop(box).convert("RGBA")
        am0 = Image.new("L", eye_p.size, 0)
        ImageDraw.Draw(am0).ellipse((1, 1, eye_p.size[0] - 2, eye_p.size[1] - 2), fill=255)
        eye_p.putalpha(am0.filter(ImageFilter.GaussianBlur(1.2)))
        sqh = max(3, int(round(eye_p.size[1] * q)))
        eye_sq = eye_p.resize((eye_p.size[0], sqh), Image.LANCZOS)
        img.alpha_composite(eye_sq, (box[0], int(cy - sqh // 2)))
    return img


# 6. write assets -----------------------------------------------------------
for d in ("base", "pupil", "pupil2", "look", "blink/0", "blink/1"):
    os.makedirs(os.path.join(ASSETS, d), exist_ok=True)

to_canvas(socket_img).save(os.path.join(ASSETS, "base", "00.png"))
sprite_on_canvas(patches[0]).save(os.path.join(ASSETS, "pupil", "00.png"))
if len(patches) > 1:
    sprite_on_canvas(patches[1]).save(os.path.join(ASSETS, "pupil2", "00.png"))

to_canvas(compose(0, 0)).save(os.path.join(ASSETS, "look", "00.png"))
to_canvas(compose(int(RANGE_BIG / SX), -1)).save(os.path.join(ASSETS, "look", "01.png"))

for bank in range(2):
    for i, q in enumerate((1.0, 0.55, 0.22, 0.06, 0.22, 0.55, 1.0)):
        to_canvas(socket_img if q >= 0.999 else blink_frame(q)).save(
            os.path.join(ASSETS, "blink", str(bank), "%02d.png" % i))

meta = {"width": CW, "height": CH, "frames": 190, "fps": 30,
        "eyeFrames": 2, "blinkFrames": 7, "blinkFps": 30,
        "pupilRange": RANGE_BIG, "pupilRange2": RANGE_SMALL,
        "eyeX": round((big["cx"] - CROP[0]) * SX + PASTE[0], 1),
        "eyeY": round((big["cy"] - CROP[1]) * SY + PASTE[1], 1)}
json.dump(meta, open(os.path.join(ASSETS, "metadata.json"), "w"), indent=1)
print("meta", meta)

nwp = os.path.join(PROJ, "素材.nwp")
missing = [n for n in os.listdir(os.path.join(ASSETS, "laugh"))] if os.path.isdir(os.path.join(ASSETS, "laugh")) else []
print("laugh frames kept:", len(missing))
with zipfile.ZipFile(nwp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, _, files in os.walk(ASSETS):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            z.write(p, os.path.relpath(p, ASSETS).replace("\\", "/"))
print("nwp MB", round(os.path.getsize(nwp) / 1e6, 2))

sheet = Image.new("RGBA", (CW * 4, CH), (30, 32, 38, 255))
for i, img in enumerate((compose(0, 0), compose(-RANGE_BIG, 0), compose(RANGE_BIG, 0), blink_frame(0.06))):
    sheet.alpha_composite(to_canvas(img), (CW * i, 0))
sheet.resize((sheet.width * 2, sheet.height * 2), Image.LANCZOS).save(os.path.join(WORK, "AF_states.png"))
print("done")
