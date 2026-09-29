"""Generate caption overlays and end card for the Nitidus pet glove ad (1080x1920)."""
import os, sys, glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
NAVY = (11, 31, 51)
YELLOW = (247, 201, 40)
WHITE = (255, 255, 255)
OUT = sys.argv[1] if len(sys.argv) > 1 else "ov"
ASSETS = sys.argv[2] if len(sys.argv) > 2 else "../product"
os.makedirs(OUT, exist_ok=True)


def find_font(names):
    for n in names:
        hits = glob.glob(f"/usr/share/fonts/**/{n}", recursive=True) + glob.glob(os.path.expanduser(f"~/.fonts/**/{n}"), recursive=True)
        if hits:
            return hits[0]
    return None


BOLD = find_font(["Montserrat-ExtraBold.ttf", "Montserrat-Bold.ttf", "Metropolis-ExtraBold.otf", "DejaVuSans-Bold.ttf"])
SEMI = find_font(["Montserrat-SemiBold.ttf", "Metropolis-SemiBold.otf", "DejaVuSans-Bold.ttf"])
REG = find_font(["Montserrat-Medium.ttf", "Metropolis-Medium.otf", "DejaVuSans.ttf"])


def f(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def caption(name, text, y=1180, size=58, highlight=None):
    """TikTok-style white rounded boxes, one per line, black text."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    font = f(BOLD, size)
    lines = wrap(d, text, font, W - 200)
    lh = size + 34
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=font)
        x0 = (W - tw) / 2 - 26
        y0 = y + i * lh
        d.rounded_rectangle([x0, y0, x0 + tw + 52, y0 + lh - 8], radius=18, fill=WHITE)
        # draw word by word so a highlight word can be yellow-boxed
        x = (W - tw) / 2
        for word in line.split():
            ww = d.textlength(word, font=font)
            if highlight and word.strip(".,!?").lower() in highlight:
                d.rounded_rectangle([x - 8, y0 + 8, x + ww + 8, y0 + lh - 16], radius=10, fill=YELLOW)
            d.text((x, y0 + 10), word, font=font, fill=(0, 0, 0))
            x += ww + d.textlength(" ", font=font)
    im.save(f"{OUT}/{name}.png")


def disclaimer():
    """Blank placeholder: no on-video AI disclaimer (per client)."""
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(f"{OUT}/disclaimer.png")


def endcard():
    im = Image.new("RGB", (W, H), (244, 246, 248))
    d = ImageDraw.Draw(im)
    # soft yellow glow behind the product
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([190, 330, 890, 1030], fill=(247, 201, 40, 90))
    im.paste(glow.filter(ImageFilter.GaussianBlur(60)), (0, 0), glow.filter(ImageFilter.GaussianBlur(60)))

    logo = Image.open(f"{ASSETS}/nitidus_logo.png").convert("RGBA")
    lw = 560
    logo = logo.resize((lw, int(logo.height * lw / logo.width)))
    im.paste(logo, ((W - lw) // 2, 120), logo)

    d.text((W / 2, 310), "The Pet Hair Glove", font=f(SEMI, 44), fill=NAVY, anchor="mm")

    # product: glove photo, cut out the light background
    g = Image.open(f"{ASSETS}/glove_back.jpg").convert("RGBA")
    g = g.crop((420, 280, 1580, 1720))
    px = g.load()
    for yy in range(g.height):
        for xx in range(g.width):
            r, gg, b, a = px[xx, yy]
            if min(r, gg, b) > 165 and max(r, gg, b) - min(r, gg, b) < 30:
                px[xx, yy] = (r, gg, b, 0)
    gh = 620
    g = g.resize((int(g.width * gh / g.height), gh))
    im.paste(g, ((W - g.width) // 2, 380), g)

    # SAVE badge
    bx, by = 830, 560
    d.ellipse([bx - 120, by - 120, bx + 120, by + 120], fill=YELLOW)
    d.text((bx, by - 38), "SAVE", font=f(BOLD, 44), fill=NAVY, anchor="mm")
    d.text((bx, by + 24), "33%", font=f(BOLD, 84), fill=NAVY, anchor="mm")

    # price line
    y = 1080
    old = "$29.95"
    fo, fn = f(SEMI, 64), f(BOLD, 128)
    ow, nw = d.textlength(old, font=fo), d.textlength("$19.95", font=fn)
    x0 = (W - (ow + 40 + nw)) / 2
    d.text((x0, y + 40), old, font=fo, fill=(130, 138, 150))
    d.line([x0 - 6, y + 80, x0 + ow + 6, y + 70], fill=(220, 50, 50), width=7)
    d.text((x0 + ow + 40, y), "$19.95", font=fn, fill=NAVY)

    # bundle tiles
    tiles = [("1 Glove", "$19.95", ""), ("2 Gloves", "$29.95", "MOST POPULAR"), ("3 Gloves", "$41.95", "BEST VALUE")]
    tw_, th_, gap = 300, 210, 24
    tx = (W - (3 * tw_ + 2 * gap)) / 2
    ty = 1270
    for i, (a, p, tag) in enumerate(tiles):
        x = tx + i * (tw_ + gap)
        hot = i == 1
        d.rounded_rectangle([x, ty, x + tw_, ty + th_], radius=26, fill=NAVY if hot else WHITE, outline=YELLOW if hot else (210, 215, 222), width=5)
        c = WHITE if hot else NAVY
        d.text((x + tw_ / 2, ty + 70), a, font=f(SEMI, 40), fill=c, anchor="mm")
        d.text((x + tw_ / 2, ty + 140), p, font=f(BOLD, 60), fill=YELLOW if hot else NAVY, anchor="mm")
        if tag:
            tf = f(BOLD, 24)
            tl = d.textlength(tag, font=tf)
            d.rounded_rectangle([x + tw_ / 2 - tl / 2 - 16, ty - 22, x + tw_ / 2 + tl / 2 + 16, ty + 20], radius=20, fill=YELLOW)
            d.text((x + tw_ / 2, ty - 1), tag, font=tf, fill=NAVY, anchor="mm")

    # CTA pill
    cy = 1570
    d.rounded_rectangle([W / 2 - 250, cy, W / 2 + 250, cy + 120], radius=60, fill=YELLOW)
    d.text((W / 2, cy + 60), "Shop Now  →", font=f(BOLD, 58), fill=NAVY, anchor="mm")

    # USP bar
    d.rectangle([0, 1760, W, H], fill=NAVY)
    usp = "Reusable  |  No sticky sheets  |  Couch, clothes & car"
    d.text((W / 2, 1840), usp, font=f(SEMI, 34), fill=YELLOW, anchor="mm")
    im.save(f"{OUT}/endcard.png")


CAPS = [
    ("c1", "POV: your in-laws just showed up unannounced", 1150, ["in-laws"]),
    ("c2", "...and then Mom stands up", 1250, ["stands"]),
    ("c3a", "I used to dread my in-laws coming over", 1250, ["dread"]),
    ("c3b", "I felt like my house was never clean enough", 1250, ["never"]),
    ("c4a", "Then I found the Nitidus Pet Hair Glove", 1250, ["nitidus"]),
    ("c4b", "One swipe. Hair rolls right off.", 1250, ["one", "swipe."]),
    ("c5", "And now? I actually love having them over", 1250, ["love"]),
    ("h1", "When your mother-in-law hugs you... and leaves wearing your dog", 1150, ["wearing", "dog"]),
    ("h2", "The in-laws are 5 minutes away. My couch:", 1150, ["5", "minutes"]),
    ("h3", "Dog moms: has your mother-in-law ever commented on the dog hair?", 1150, ["mother-in-law"]),
]

if __name__ == "__main__":
    for name, text, y, hl in CAPS:
        caption(name, text, y=y, highlight=[h.lower() for h in hl])
    disclaimer()
    endcard()
    print("fonts:", BOLD, SEMI, REG)
