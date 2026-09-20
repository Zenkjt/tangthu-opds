#!/usr/bin/env python3
"""Generate the Tàng Thư bookshelf image assets.

Asset generator only.
It does NOT modify OPDS generation, pagination, registration,
or the bookshelf HTML/CSS pipeline.

Run from repository root:
    python3 scripts/generate_bookshelf_assets.py
"""

from PIL import Image, ImageDraw, ImageFilter
import math
import os

OUT = os.path.join("docs", "assets", "bookshelf")
os.makedirs(OUT, exist_ok=True)

W = H = 256


def rounded(d, box, radius, fill, outline=None, width=1):
    d.rounded_rectangle(
        box, radius=radius, fill=fill, outline=outline, width=width
    )


def draw_logo(d, logo, color):
    """Small upper logo; the lower book face stays completely clean.

    The bookshelf name/statistics are intentionally NOT drawn into the PNG.
    The UI renders them outside the book icon on a transparent background.
    """
    lc = (245, 239, 210, 255)

    if logo == "columns":
        d.rectangle((124, 76, 146, 79), fill=lc)
        for x in (126, 134, 142):
            d.rectangle((x, 57, x + 3, 76), fill=lc)
        d.arc((122, 50, 148, 65), 180, 360, fill=lc, width=2)
        d.line((123, 57, 147, 57), fill=lc, width=2)

    elif logo == "globe":
        d.ellipse((120, 50, 150, 80), outline=lc, width=2)
        d.arc((120, 50, 150, 80), 90, 270, fill=lc, width=2)
        d.arc((120, 50, 150, 80), 270, 90, fill=lc, width=2)
        d.line((135, 50, 135, 80), fill=lc, width=2)
        d.line((122, 65, 148, 65), fill=lc, width=2)

    elif logo == "leaf":
        d.ellipse((123, 51, 148, 76), outline=lc, width=2)
        d.polygon([(126, 74), (144, 57), (139, 75)], fill=lc)
        d.line((130, 78, 145, 60), fill=lc, width=2)

    elif logo == "atom":
        for ang in (0, 60, 120):
            pts = []
            a = math.radians(ang)
            for t in range(0, 361, 12):
                tt = math.radians(t)
                x = 135 + 18 * math.cos(tt)
                y = 65 + 8 * math.sin(tt)
                pts.append(
                    (
                        135 + (x - 135) * math.cos(a)
                        - (y - 65) * math.sin(a),
                        65 + (x - 135) * math.sin(a)
                        + (y - 65) * math.cos(a),
                    )
                )
            d.line(pts, fill=lc, width=2)
        d.ellipse((132, 62, 138, 68), fill=lc)

    elif logo == "book":
        d.rectangle((124, 53, 134, 75), outline=lc, width=2)
        d.rectangle((136, 53, 146, 75), outline=lc, width=2)
        d.line((135, 54, 135, 76), fill=lc, width=2)
        d.arc((122, 48, 136, 59), 180, 350, fill=lc, width=2)
        d.arc((134, 48, 148, 59), 190, 360, fill=lc, width=2)

    elif logo == "gear":
        d.ellipse((123, 53, 147, 77), outline=lc, width=3)
        d.ellipse((131, 61, 139, 69), outline=lc, width=2)
        for ang in range(0, 360, 45):
            a = math.radians(ang)
            d.line(
                (
                    135 + 15 * math.cos(a),
                    65 + 15 * math.sin(a),
                    135 + 19 * math.cos(a),
                    65 + 19 * math.sin(a),
                ),
                fill=lc,
                width=2,
            )


def make_book(color, logo):
    # Transparent canvas: no title/statistics box is baked into the asset.
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Soft shadow.
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    rounded(sd, (44, 22, 219, 231), 14, (0, 0, 0, 70))
    im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))

    d = ImageDraw.Draw(im)

    # Pages / top / outer spine.
    d.polygon(
        [(58, 25), (204, 20), (219, 31), (73, 39)],
        fill=(238, 231, 211, 255),
        outline=(25, 25, 25, 255),
    )
    d.polygon(
        [(204, 20), (219, 31), (219, 214), (205, 226)],
        fill=(222, 215, 196, 255),
        outline=(25, 25, 25, 255),
    )

    # Spine and cover.
    rounded(d, (42, 39, 72, 226), 7, color, (10, 10, 10, 255), 3)
    rounded(d, (65, 34, 205, 226), 7, color, (8, 8, 8, 255), 4)

    # Inner border uses the same cover colour family.
    r, g, b, _ = color
    d.rounded_rectangle(
        (72, 42, 198, 218),
        5,
        outline=(max(0, r - 20), max(0, g - 20), max(0, b - 20), 255),
        width=2,
    )

    # Small logo near the top. Nothing is placed over the lower cover.
    draw_logo(d, logo, color)

    return im


SPECS = [
    ("book-blue.png", (30, 105, 205, 255), "columns"),
    ("book-brown.png", (150, 88, 25, 255), "globe"),
    ("book-green.png", (24, 145, 91, 255), "leaf"),
    ("book-purple.png", (110, 55, 175, 255), "atom"),
    ("book-red.png", (190, 35, 45, 255), "book"),
    ("book-teal.png", (25, 145, 170, 255), "gear"),
]

for name, color, logo in SPECS:
    make_book(color, logo).save(
        os.path.join(OUT, name),
        optimize=True,
    )


# Shared transparent-background wooden shelf.
im = Image.new("RGBA", (768, 180), (0, 0, 0, 0))
d = ImageDraw.Draw(im)

rounded(
    d,
    (18, 25, 55, 155),
    8,
    (135, 83, 20, 255),
    (65, 40, 10, 255),
    4,
)
rounded(
    d,
    (713, 25, 750, 155),
    8,
    (135, 83, 20, 255),
    (65, 40, 10, 255),
    4,
)
rounded(
    d,
    (38, 108, 730, 151),
    6,
    (145, 88, 22, 255),
    (67, 39, 9, 255),
    4,
)
d.rectangle((45, 116, 723, 141), fill=(177, 111, 31, 255))
rounded(
    d,
    (32, 101, 736, 119),
    5,
    (166, 100, 25, 255),
    (73, 42, 10, 255),
    3,
)

im.save(
    os.path.join(OUT, "shelf-row.png"),
    optimize=True,
)

print("Generated:", OUT)
