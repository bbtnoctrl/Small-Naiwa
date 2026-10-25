// 把 Naiwa.cs 里 Renderer.WarpBelly 的算法原样抄出来，用于和 Python 版逐像素比对
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

class WarpCheck
{
    internal static Bitmap WarpBelly(Bitmap original, double cx, double cy, double amount)
    {
        int w = original.Width, h = original.Height; byte[] source = new byte[w * h * 4];
        BitmapData locked = original.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadOnly, PixelFormat.Format32bppPArgb);
        try { Marshal.Copy(locked.Scan0, source, 0, source.Length); } finally { original.UnlockBits(locked); }
        byte[] result = (byte[])source.Clone();
        const double radiusX = 98, radiusY = 86;
        int left = Math.Max(0, (int)(cx - radiusX)), right = Math.Min(w - 2, (int)(cx + radiusX));
        int top = Math.Max(127, (int)(cy - radiusY)), bottom = Math.Min(Math.Min(291, h - 2), (int)(cy + radiusY));
        for (int y = top; y <= bottom; y++) for (int x = left; x <= right; x++)
        {
            double dx = x - cx, dy = y - cy, r = dx * dx / (radiusX * radiusX) + dy * dy / (radiusY * radiusY); if (r >= 1) continue;
            double neck = Math.Min(1, (y - 127) / 28.0), legs = Math.Min(1, (291 - y) / 22.0);
            double fade = neck * neck * (3 - 2 * neck) * legs * legs * (3 - 2 * legs);
            double fall = (1 - r) * (1 - r) * amount * fade;
            double sx = Math.Max(0, Math.Min(w - 1.001, x + dx * fall)), sy = Math.Max(0, Math.Min(h - 1.001, y + dy * fall * .6));
            int ix = Math.Max(0, Math.Min(w - 2, (int)sx)), iy = Math.Max(0, Math.Min(h - 2, (int)sy)); double fx = sx - ix, fy = sy - iy;
            int dest = (y * w + x) * 4, a = (iy * w + ix) * 4, b = a + 4, c = a + w * 4, d = c + 4;
            for (int channel = 0; channel < 4; channel++)
                result[dest + channel] = (byte)Math.Max(0, Math.Min(255, (source[a + channel] * (1 - fx) + source[b + channel] * fx) * (1 - fy) + (source[c + channel] * (1 - fx) + source[d + channel] * fx) * fy));
        }
        Bitmap warped = new Bitmap(w, h, PixelFormat.Format32bppPArgb);
        locked = warped.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.WriteOnly, PixelFormat.Format32bppPArgb);
        try { Marshal.Copy(result, 0, locked.Scan0, result.Length); } finally { warped.UnlockBits(locked); }
        return warped;
    }

    static void Main(string[] args)
    {
        string src = args[0], dst = args[1];
        double cx = double.Parse(args[2]), cy = double.Parse(args[3]), amount = double.Parse(args[4]);
        using (Bitmap img = new Bitmap(src)) { using (Bitmap w = WarpBelly(img, cx, cy, amount)) { w.Save(dst, ImageFormat.Png); } }
        Console.WriteLine("ok");
    }
}
