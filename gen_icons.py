#!/usr/bin/env python3
"""
「粹」手作烘焙 PWA 圖示產生器
================================
預設會使用 images/logo.png 的「廚師帽圓形圖案」製作所有圖示，
底色自動取自 Logo 本身，因此圖形與背景無縫融合。
若 images/logo.png 不存在，則改用「粹」字 + 品牌色。

執行後輸出：
    icons/icon-72/96/128/144/152/192/384/512.png   一般圖示 (圓角、透明邊角)
    icons/maskable-192/512.png                      Android 自適應圖示 (滿版，內容在安全區)
    icons/apple-touch-icon.png (180x180)            iOS 主畫面圖示 (滿版、不透明)
    icons/favicon-16/32.png、favicon.ico            瀏覽器分頁圖示
    images/logo-mark.png                            Logo 圖形部分 (網頁頁首、頁尾使用)

使用方式：
    pip install pillow
    python gen_icons.py                              # 使用 images/logo.png
    python gen_icons.py --logo path/to/logo.png      # 指定其他 Logo
    python gen_icons.py --crop 0.1595,0.0223,0.6858  # 調整圖形裁切 (左,上,邊長；相對圖片寬度)
    python gen_icons.py --no-logo                    # 強制使用文字圖示
    python gen_icons.py --char 粹 --font 字型檔       # 文字模式：指定文字與字型
"""

import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 文字模式的品牌色 (對應 index.html 的 brand 色票) ───────────────
BG = (78, 61, 43)           # brand-dark   #4E3D2B
RING = (140, 98, 57)        # brand-accent #8C6239
FG = (254, 241, 222)        # brand-light  #FEF1DE

MASTER = 1024               # 以大尺寸繪製再縮小，邊緣較平滑
ANY_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
MASKABLE_SIZES = [192, 512]

# Logo 圖形預設裁切 (左, 上, 邊長)，皆為相對圖片寬度的比例。
# 預設框住上方「廚師帽圓形」，不含下方「粹 手作烘焙」文字。
DEFAULT_CROP = (0.1595, 0.0223, 0.6858)

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-SemiBold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "C:/Windows/Fonts/msjhbd.ttc",
    "C:/Windows/Fonts/msjh.ttc",
    "C:/Windows/Fonts/mingliu.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


# ───────────────────────── Logo 模式 ─────────────────────────
def extract_mark(logo, crop):
    """依比例裁出 Logo 的圖形部分 (正方形)。"""
    w = logo.width
    left, top, side = (int(round(v * w)) for v in crop)
    side = min(side, logo.width - left, logo.height - top)
    return logo.crop((left, top, left + side, top + side))


def circle_paste(canvas, face, diameter):
    """把 face 縮成圓形貼到畫布正中央。"""
    face = face.resize((diameter, diameter), Image.LANCZOS)
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
    pos = (MASTER - diameter) // 2
    canvas.paste(face, (pos, pos), mask)


# ───────────────────────── 文字模式 ─────────────────────────
def load_font(path, size):
    """載入字型；若為 .ttc 集合檔，優先挑選繁體中文 (TC) 字面。"""
    if path.lower().endswith(".ttc"):
        fallback = None
        for index in range(12):
            try:
                font = ImageFont.truetype(path, size, index=index)
            except (OSError, IndexError):
                break
            if fallback is None:
                fallback = font
            family = " ".join(font.getname())
            if "TC" in family or "Traditional" in family or "JhengHei" in family:
                return font
        if fallback is not None:
            return fallback
    return ImageFont.truetype(path, size)


def find_font(user_path, size):
    paths = [user_path] if user_path else FONT_CANDIDATES
    for p in paths:
        if p and os.path.exists(p):
            try:
                return load_font(p, size)
            except OSError:
                continue
    sys.exit(
        "找不到可顯示中文的字型。\n"
        "請用 --font 指定字型檔，例如：\n"
        "  python gen_icons.py --no-logo --font C:/Windows/Fonts/msjh.ttc"
    )


# ───────────────────────── 繪製母圖 ─────────────────────────
def draw_master(safe_scale, rounded, bg, mark=None, char="粹", font_path=None):
    """
    繪製 1024x1024 母圖。
    safe_scale: 圖形佔畫布的比例 (maskable 要縮在安全區內)
    rounded   : True → 圓角矩形 + 透明邊角；False → 滿版方形
    mark      : Logo 圖形 (PIL Image)；None 則改畫文字
    """
    size = MASTER
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if rounded:
        draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.22), fill=bg)
    else:
        draw.rectangle((0, 0, size, size), fill=bg)

    diameter = int(size * safe_scale)
    if mark is not None:
        circle_paste(img, mark, diameter)
        return img

    c = size // 2
    r = diameter // 2
    draw.ellipse((c - r, c - r, c + r, c + r), outline=RING, width=max(6, size // 100))
    font = find_font(font_path, int(diameter * 0.62))
    bbox = draw.textbbox((0, 0), char, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((c - w / 2 - bbox[0], c - h / 2 - bbox[1]), char, font=font, fill=FG)
    return img


def save_resized(master, px, path):
    master.resize((px, px), Image.LANCZOS).save(path, optimize=True)
    print(f"  ✓ {os.path.relpath(path, HERE)}  ({px}x{px})")


def main():
    parser = argparse.ArgumentParser(description="產生 PWA 圖示")
    parser.add_argument("--logo", default=os.path.join(HERE, "images", "logo.png"),
                        help="Logo 圖片路徑 (預設：images/logo.png)")
    parser.add_argument("--crop", help="Logo 圖形裁切 '左,上,邊長' (相對圖片寬度的比例)")
    parser.add_argument("--no-logo", action="store_true", help="不使用 Logo，改用文字圖示")
    parser.add_argument("--char", default="粹", help="文字模式的中央文字 (預設：粹)")
    parser.add_argument("--font", help="文字模式的 CJK 字型檔 (.ttf/.otf/.ttc)")
    parser.add_argument("--out", default="icons", help="圖示輸出資料夾 (預設：icons)")
    args = parser.parse_args()

    out = os.path.join(HERE, args.out)
    os.makedirs(out, exist_ok=True)

    mark, bg = None, BG
    if not args.no_logo and os.path.exists(args.logo):
        logo = Image.open(args.logo).convert("RGB")
        crop = tuple(float(v) for v in args.crop.split(",")) if args.crop else DEFAULT_CROP
        mark = extract_mark(logo, crop)
        bg = logo.getpixel((3, 3))  # 取 Logo 左上角像素當底色，圖形與背景無縫融合
        print(f"使用 Logo：{os.path.relpath(args.logo, HERE)}　底色：#{bg[0]:02X}{bg[1]:02X}{bg[2]:02X}")

        # 輸出網頁用的 Logo 圖形
        mark_path = os.path.join(HERE, "images", "logo-mark.png")
        os.makedirs(os.path.dirname(mark_path), exist_ok=True)
        mark.resize((512, 512), Image.LANCZOS).save(mark_path, optimize=True)
        print(f"  ✓ {os.path.relpath(mark_path, HERE)}  (512x512)")
    else:
        print("未使用 Logo，改用文字圖示")

    kw = dict(bg=bg, mark=mark, char=args.char, font_path=args.font)

    print("產生一般圖示 (any)…")
    any_master = draw_master(0.74, True, **kw)
    for s in ANY_SIZES:
        save_resized(any_master, s, os.path.join(out, f"icon-{s}.png"))

    print("產生 Maskable 圖示…")
    mask_master = draw_master(0.62, False, **kw)   # 安全區為中央 80% 圓形
    for s in MASKABLE_SIZES:
        save_resized(mask_master, s, os.path.join(out, f"maskable-{s}.png"))

    print("產生 iOS Apple Touch Icon…")
    apple_master = draw_master(0.70, False, **kw)
    save_resized(apple_master.convert("RGB"), 180, os.path.join(out, "apple-touch-icon.png"))

    print("產生 Favicon…")
    for s in (16, 32):
        save_resized(any_master, s, os.path.join(out, f"favicon-{s}.png"))
    any_master.resize((64, 64), Image.LANCZOS).save(
        os.path.join(out, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)]
    )
    print(f"  ✓ {os.path.relpath(os.path.join(out, 'favicon.ico'), HERE)}")
    print("\n完成！")


if __name__ == "__main__":
    main()
