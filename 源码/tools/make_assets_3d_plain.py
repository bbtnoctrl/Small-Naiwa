"""最保守版本：眼球用视频原图，不做任何合成（不追鼠标），眨眼仍是整只眼压扁。"""
import os, json, shutil, zipfile
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

f = Image.open(os.path.join(SRC, "%04d.png" % IDLE)).convert("RGBA")
a = np.asarray(f).astype(np.int16)
rgb = a[:, :, :3]; alpha = a[:, :, 3]
lum = rgb.mean(axis=2)
H, W = lum.shape
yy, xx = np.mgrid[0:H, 0:W]

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
            ys, xs = np.where(cur)
            out.append((float(xs.mean()), float(ys.mean()), float(np.sqrt(cur.sum() / np.pi))))
        idx = np.argwhere(mask & ~seen)
    return out


dark = (lum < 85) & (alpha > 128)
dark[180:, :] = False
eyes = sorted([e for e in components(dark, 350) if e[0] < 260], key=lambda t: -t[2])
big = eyes[0]
print("eyes", [(round(x, 1), round(y, 1), round(r, 1)) for x, y, r in eyes])

# face colour for the lid
skin_rgb = rgb.astype(np.float32).copy()
for cx, cy, r in eyes:
    R2 = r + 20.0
    cheek = np.zeros((H, W), bool)
    x1 = min(W, int(cx + 3.6 * r)); x0 = min(x1 - 2, int(cx + 1.6 * r))
    y0 = max(0, int(cy - 1.2 * r)); y1 = min(H, int(cy + 1.6 * r))
    cheek[y0:y1, x0:x1] = True
    cheek &= (alpha > 220)
    face_col = np.median(rgb[cheek], axis=0) if int(cheek.sum()) else np.array([232, 196, 92], np.float32)
    dist_m = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    t = np.clip((yy - (cy - R2)) / (2 * R2), 0, 1)[:, :, None]
    fill = face_col[None, None, :] * (1.03 - 0.08 * t)
    w = np.clip((R2 - dist_m) / max(1.0, R2 - (r + 8.0)), 0, 1)[:, :, None]
    skin_rgb = np.where((dist_m <= R2)[:, :, None], skin_rgb * (1 - w) + fill * w, skin_rgb)
skin = Image.fromarray(np.dstack([skin_rgb.clip(0, 255).astype(np.uint8),
                                  alpha.clip(0, 255).astype(np.uint8)]), "RGBA")


def blink_frame(q):
    img = skin.copy()
    for cx, cy, r in eyes:
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


shutil.rmtree(os.path.join(ASSETS, "pupil"), ignore_errors=True)
shutil.rmtree(os.path.join(ASSETS, "pupil2"), ignore_errors=True)
for d in ("base", "look", "blink/0", "blink/1"):
    os.makedirs(os.path.join(ASSETS, d), exist_ok=True)

to_canvas(f).save(os.path.join(ASSETS, "base", "00.png"))
to_canvas(f).save(os.path.join(ASSETS, "look", "00.png"))
to_canvas(f).save(os.path.join(ASSETS, "look", "01.png"))
for bank in range(2):
    for i, q in enumerate((1.0, 0.55, 0.22, 0.06, 0.22, 0.55, 1.0)):
        to_canvas(f if q >= 0.999 else blink_frame(q)).save(
            os.path.join(ASSETS, "blink", str(bank), "%02d.png" % i))

meta = {"width": CW, "height": CH, "frames": 190, "fps": 30,
        "eyeFrames": 2, "blinkFrames": 7, "blinkFps": 30}
json.dump(meta, open(os.path.join(ASSETS, "metadata.json"), "w"), indent=1)
print("meta", meta)

nwp = os.path.join(PROJ, "素材.nwp")
with zipfile.ZipFile(nwp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, _, files in os.walk(ASSETS):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            z.write(p, os.path.relpath(p, ASSETS).replace("\\", "/"))
print("nwp MB", round(os.path.getsize(nwp) / 1e6, 2))

sheet = Image.new("RGBA", (CW * 3, CH), (30, 32, 38, 255))
for i, img in enumerate((f, blink_frame(0.22), blink_frame(0.06))):
    sheet.alpha_composite(to_canvas(img), (CW * i, 0))
sheet.resize((sheet.width * 2, sheet.height * 2), Image.LANCZOS).save(os.path.join(WORK, "AM_plain.png"))
print("done")
