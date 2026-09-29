"""Static image ads for the Nitidus 50+ mums set.

usage: python3 statics.py <bg_dir> <assets_dir> <out_dir>
bg_dir holds: grandkids.png backpain.png lintroller.png hairy.png presenter.png
assets_dir holds: nitidus_logo.png glove_back.jpg glove_hair_dog.jpg
Writes <name>_4x5.jpg (1080x1350 feed) and <name>_9x16.jpg (1080x1920 stories).
"""
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BG, ASSETS, OUT = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)
NAVY = (11, 31, 51)
YELLOW = (247, 201, 40)
WHITE = (255, 255, 255)


def font(names, size):
    for n in names:
        hits = glob.glob(f"/usr/share/fonts/**/{n}", recursive=True)
        if hits:
            return ImageFont.truetype(hits[0], size)
    raise SystemExit(f"no font among {names}")


def BOLD(s):
    return font(["Montserrat-ExtraBold.ttf", "Montserrat-Bold.ttf", "DejaVuSans-Bold.ttf"], s)


def SEMI(s):
    return font(["Montserrat-SemiBold.ttf", "Montserrat-Bold.ttf", "DejaVuSans-Bold.ttf"], s)


def cover(img, w, h, focus_y=0.4):
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s) + 1, int(img.height * s) + 1))
    top = int((img.height - h) * focus_y)
    left = (img.width - w) // 2
    return img.crop((left, top, left + w, top + h))


def wrap(d, text, f, maxw):
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    return out


def shade(im, top_h, bottom_h):
    """Dark gradients top and bottom so white text reads on any photo."""
    w, h = im.size
    g = Image.new("L", (1, h), 0)
    for y in range(h):
        a = 0
        if y < top_h:
            a = int(200 * (1 - y / top_h))
        elif y > h - bottom_h:
            a = int(215 * ((y - (h - bottom_h)) / bottom_h))
        g.putpixel((0, y), a)
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, im, g.resize((w, h)))


def headline(d, lines_spec, y, w, size):
    """lines_spec: list of (text, color). Big bold, centered, shadowed."""
    f = BOLD(size)
    for text, col in lines_spec:
        for line in wrap(d, text, f, w - 110):
            tw = d.textlength(line, font=f)
            x = (w - tw) / 2
            d.text((x + 3, y + 4), line, font=f, fill=(0, 0, 0))
            d.text((x, y), line, font=f, fill=col)
            y += int(size * 1.08)
    return y


def logo(im, y, width=300):
    lg = Image.open(f"{ASSETS}/nitidus_logo.png").convert("RGBA")
    lg = lg.resize((width, int(lg.height * width / lg.width)))
    pad = Image.new("RGBA", (lg.width + 44, lg.height + 30), (255, 255, 255, 235))
    pad.paste(lg, (22, 15), lg)
    m = Image.new("L", pad.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, pad.width, pad.height], 22, fill=255)
    im.paste(pad, ((im.width - pad.width) // 2, y), m)


def price_block(im, d, y):
    w = im.width
    fo, fn = SEMI(50), BOLD(96)
    old, new = "$50", "$29.95"
    ow, nw = d.textlength(old, font=fo), d.textlength(new, font=fn)
    x0 = (w - (ow + 30 + nw)) / 2
    d.text((x0 + 2, y + 34), old, font=fo, fill=(0, 0, 0))
    d.text((x0, y + 32), old, font=fo, fill=(225, 225, 225))
    d.line([x0 - 4, y + 64, x0 + ow + 4, y + 56], fill=(230, 60, 60), width=6)
    d.text((x0 + ow + 33, y + 3), new, font=fn, fill=(0, 0, 0))
    d.text((x0 + ow + 30, y), new, font=fn, fill=YELLOW)
    return y + 112


def bundles(d, y, w):
    f = SEMI(34)
    t = "2 for $49.95   |   3 for $64.95"
    tw = d.textlength(t, font=f)
    d.rounded_rectangle([(w - tw) / 2 - 26, y, (w + tw) / 2 + 26, y + 58], 29, fill=(255, 255, 255))
    d.text((w / 2, y + 29), t, font=f, fill=NAVY, anchor="mm")
    return y + 58


def cta(d, y, w, text="Shop Now"):
    d.rounded_rectangle([w / 2 - 210, y, w / 2 + 210, y + 100], 50, fill=YELLOW)
    d.text((w / 2, y + 50), text + "  →", font=BOLD(50), fill=NAVY, anchor="mm")
    return y + 100


def usp_bar(d, w, h):
    d.rectangle([0, h - 76, w, h], fill=YELLOW)
    d.text((w / 2, h - 38), "Reusable  •  No sticky sheets  •  Couch, clothes & car",
           font=SEMI(29), fill=NAVY, anchor="mm")


def glove_inset(im, x, y, size, src="glove_back.jpg", crop=(420, 280, 1580, 1720)):
    g = Image.open(f"{ASSETS}/{src}").convert("RGB")
    if crop:
        g = g.crop(crop)
    g = cover(g, size, size, 0.5)
    card = Image.new("RGB", (size + 16, size + 16), WHITE)
    card.paste(g, (8, 8))
    m = Image.new("L", card.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, card.width, card.height], 28, fill=255)
    sh = Image.new("RGBA", (card.width + 40, card.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([20, 24, card.width + 20, card.height + 24], 30, fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    im.paste(sh, (x - 20, y - 20), sh)
    im.paste(card, (x, y), m)


def standard(name, bg, head, focus=0.35, inset=None, cta_text="Shop Now"):
    for tag, (W, H) in {"4x5": (1080, 1350), "9x16": (1080, 1920)}.items():
        im = cover(Image.open(f"{BG}/{bg}").convert("RGB"), W, H, focus)
        tall = H > 1500
        im = shade(im, 560 if tall else 470, 700 if tall else 560)
        d = ImageDraw.Draw(im)
        top = 150 if tall else 70
        logo(im, top, 260)
        y = headline(d, head, top + 120, W, 84 if tall else 74)
        if inset:
            s = 300 if tall else 250
            glove_inset(im, W - s - 60, y + 30, s, *inset)
        base = H - 76 - (520 if tall else 430)
        y = price_block(im, d, base)
        y = bundles(d, y + 22, W)
        cta(d, y + 34, W, cta_text)
        usp_bar(d, W, H)
        im.save(f"{OUT}/{name}_{tag}.jpg", quality=92)


def before_after():
    for tag, (W, H) in {"4x5": (1080, 1350), "9x16": (1080, 1920)}.items():
        tall = H > 1500
        im = Image.new("RGB", (W, H), NAVY)
        d = ImageDraw.Draw(im)
        top = 150 if tall else 60
        logo(im, top, 240)
        y = headline(d, [("One swipe. That's it.", WHITE)], top + 105, W, 78 if tall else 68)
        ph = (H - 76 - (500 if tall else 400)) - (y + 30)
        pw = (W - 3 * 30) // 2
        left = cover(Image.open(f"{BG}/hairy.png").convert("RGB"), pw, ph, 0.62)
        right = cover(Image.open(f"{ASSETS}/glove_hair_dog.jpg").convert("RGB"), pw, ph, 0.55)
        for i, (p, lab, col) in enumerate([(left, "BEFORE", (230, 60, 60)), (right, "AFTER 1 SWIPE", YELLOW)]):
            x = 30 + i * (pw + 30)
            m = Image.new("L", p.size, 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, pw, ph], 26, fill=255)
            im.paste(p, (x, y + 30), m)
            lf = BOLD(34)
            lw = d.textlength(lab, font=lf)
            d.rounded_rectangle([x + 20, y + 50, x + 20 + lw + 36, y + 110], 30, fill=col)
            d.text((x + 38 + lw / 2, y + 80), lab, font=lf, fill=NAVY if col == YELLOW else WHITE, anchor="mm")
        base = H - 76 - (470 if tall else 380)
        yy = price_block(im, d, base)
        yy = bundles(d, yy + 18, W)
        cta(d, yy + 28, W)
        usp_bar(d, W, H)
        im.save(f"{OUT}/beforeafter_{tag}.jpg", quality=92)


standard("grandkids", "grandkids.png",
         [("Guest-ready", YELLOW), ("before the grandkids arrive", WHITE)], focus=0.3)
standard("backpain", "backpain.png",
         [("No bending.", WHITE), ("No vacuum.", WHITE), ("No sore back.", YELLOW)], focus=0.3,
         inset=("glove_back.jpg", (420, 280, 1580, 1720)))
standard("lintroller", "lintroller.png",
         [("Still buying", WHITE), ("lint roller refills?", YELLOW)], focus=0.3,
         inset=("glove_back.jpg", (420, 280, 1580, 1720)))
standard("bundle", "presenter.png",
         [("One for the couch.", WHITE), ("One for the car.", WHITE), ("One for your daughter.", YELLOW)],
         focus=0.2, cta_text="Get 3 Now")
before_after()
print("done", sorted(os.listdir(OUT)))
