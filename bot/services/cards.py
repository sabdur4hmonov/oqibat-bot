"""Original vector icons and glyph-safe Pillow cards; no emoji font needed."""

import unicodedata
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from bot import texts

FONT = Path(__file__).resolve().parents[2] / "assets/fonts/NotoSans.ttf"
SIZE, STORY_SIZE = (1080, 1080), (1080, 1920)
RANK_COLORS = ("#f5cc72", "#c6d4e1", "#d9a17c")


@lru_cache(maxsize=16)
def font(size):
    return ImageFont.truetype(str(FONT), size)


@lru_cache(maxsize=4096)
def glyph(char):
    return bytes(font(32).getmask(char)) != bytes(font(32).getmask("\u0378"))


def plain_line(value):
    return " ".join(
        "".join(
            char for char in str(value)[:512] if not unicodedata.category(char).startswith("C")
        ).split()
    )


def safe_line(value):
    return "".join(
        char if glyph(char) else "?" if char.isalnum() else "" for char in plain_line(value)
    ).strip()


def fit_text(value, face, width):
    value = safe_line(value)
    if face.getlength(value) <= width:
        return value
    low, high = 0, len(value)
    while low < high:
        middle = (low + high + 1) // 2
        if face.getlength(value[:middle] + "…") <= width:
            low = middle
        else:
            high = middle - 1
    return value[:low] + "…"


def draw_icon(draw, kind, x, y, size, color):
    """Original marks on a normalized 100-unit canvas."""

    def box(a, b, c, d):
        return (x + a * size / 100, y + b * size / 100, x + c * size / 100, y + d * size / 100)

    width = max(2, size // 16)

    def line(points):
        draw.line(
            [(x + a * size / 100, y + b * size / 100) for a, b in points],
            fill=color,
            width=width,
            joint="curve",
        )

    def ring(bounds):
        draw.ellipse(box(*bounds), outline=color, width=width)

    if kind == "duel":
        draw.rounded_rectangle(box(12, 12, 88, 88), radius=size // 8, outline=color, width=width)
        for a, b in ((30, 30), (70, 30), (50, 50), (30, 70), (70, 70)):
            draw.ellipse(box(a - 5, b - 5, a + 5, b + 5), fill=color)
    elif kind == "mafia":
        draw.rounded_rectangle(box(5, 25, 95, 75), radius=size // 5, fill=color)
        for a in (25, 65):
            draw.ellipse(box(a - 6, 38, a + 16, 57), fill="#112836")
    elif kind == "secret":
        ring((10, 5, 70, 65))
        line([(62, 60), (92, 90)])
    elif kind == "hyj":
        for inset in (5, 24, 43):
            ring((inset, inset, 100 - inset, 100 - inset))
    elif kind == "memory":
        draw.rounded_rectangle(box(5, 25, 95, 85), radius=size // 12, outline=color, width=width)
        line([(28, 25), (35, 12), (65, 12), (72, 25)])
        ring((32, 36, 68, 72))
    elif kind == "kim":
        draw.rounded_rectangle(box(7, 10, 88, 70), radius=size // 8, outline=color, width=width)
        line([(42, 70), (25, 90), (25, 70)])
        line([(25, 32), (70, 32)])
        line([(25, 49), (55, 49)])
    elif kind == "telephone":
        draw.arc(box(10, 5, 90, 90), 30, 220, fill=color, width=width * 2)
        for a, b in ((12, 9), (65, 63)):
            draw.rounded_rectangle(box(a, b, a + 25, b + 30), radius=size // 12, fill=color)
    elif kind == "number":
        for offset in (30, 65):
            line([(offset, 10), (offset, 90)])
            line([(10, offset), (90, offset)])
    elif kind == "math":
        for points in (
            [(12, 25), (44, 25)],
            [(28, 9), (28, 41)],
            [(65, 25), (95, 25)],
            [(15, 62), (42, 89)],
            [(15, 89), (42, 62)],
            [(65, 65), (95, 65)],
            [(65, 82), (95, 82)],
        ):
            line(points)
    elif kind == "krokodil":
        line([(10, 30), (80, 30), (95, 50), (25, 50), (10, 30), (25, 80), (85, 80)])
        for a in (35, 55, 75):
            line([(a, 50), (a + 7, 65), (a + 14, 50)])
    elif kind == "quiz":
        draw.arc(box(25, 8, 75, 60), 180, 480, fill=color, width=width)
        line([(50, 60), (50, 70)])
        draw.ellipse(box(45, 82, 55, 92), fill=color)
    elif kind == "wyr":
        line([(10, 30), (90, 30), (70, 10)])
        line([(90, 70), (10, 70), (30, 90)])
    elif kind == "rps":
        for a, b in ((50, 20), (20, 75), (80, 75)):
            ring((a - 14, b - 14, a + 14, b + 14))
        for points in ([(38, 38), (28, 52)], [(43, 75), (57, 75)], [(72, 52), (62, 38)]):
            line(points)
    else:
        line([(20, 10), (80, 10), (70, 55), (50, 65), (30, 55), (20, 10)])
        line([(50, 65), (50, 90), (25, 90), (75, 90)])
        draw.arc(box(0, 15, 40, 60), 60, 270, fill=color, width=width)
        draw.arc(box(60, 15, 100, 60), 270, 480, fill=color, width=width)


def avatar(image, draw, name, photo, x, y, size, accent):
    if photo:
        try:
            with Image.open(BytesIO(photo)) as source:
                crop = ImageOps.fit(source.convert("RGB"), (size, size))
            mask = Image.new("L", (size, size))
            ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
            image.paste(crop, (x, y), mask)
            return
        except (OSError, ValueError):
            pass
    draw.ellipse((x, y, x + size, y + size), fill=accent)
    initials = "".join(word[0] for word in safe_line(name).split()[:2]).upper() or "?"
    draw.text(
        (x + size // 2, y + size // 2), initials, font=font(size // 3), fill="#112836", anchor="mm"
    )


def render_card(
    title, rows, instagram, subtitle=None, *, kind="weekly", story=False, avatars=None, levels=None
) -> bytes:
    size = STORY_SIZE if story else SIZE
    accent = texts.GAME_STYLE.get(kind, (None, None, "#57d9be"))[2]
    image = Image.new("RGB", size, "#0b1d29")
    draw = ImageDraw.Draw(image)
    draw.ellipse((650, -210, 1400, 540), fill="#113b43")
    draw.ellipse((-410, size[1] - 400, 450, size[1] + 400), fill="#102e3d")
    draw.rounded_rectangle((54, 54, 1026, size[1] - 54), radius=40, outline="#294652", width=2)
    draw.text((92, 87), texts.CARD_BRAND, font=font(28), fill=accent)
    draw_icon(draw, kind, 870, 91, 108, accent)
    top, heading_y, spacing = (520, 320, 185) if story else (280, 155, 128)
    draw.text((90, heading_y), fit_text(title, font(48), 760), font=font(48), fill="#f7f1e8")
    draw.text(
        (92, heading_y + 72),
        fit_text(subtitle or texts.SLOGAN, font(26), 850),
        font=font(26),
        fill="#abc7cd",
    )
    for index, (name, score) in enumerate(rows[:5]):
        y = top + index * spacing
        rank_color = RANK_COLORS[index] if index < 3 else accent
        draw.rounded_rectangle((78, y, 1002, y + spacing - 14), radius=24, fill="#173443")
        draw.ellipse((96, y + 29, 148, y + 81), fill=rank_color)
        draw.text((122, y + 55), str(index + 1), font=font(27), fill="#112836", anchor="mm")
        photo = avatars[index] if avatars and index < len(avatars) else None
        avatar(image, draw, name, photo, 168, y + 17, 80, rank_color)
        draw.text((270, y + 19), fit_text(name, font(32), 450), font=font(32), fill="#f7f1e8")
        label = levels[index] if levels and index < len(levels) else texts.CARD_RANK
        draw.text((271, y + 67), fit_text(label, font(20), 450), font=font(20), fill="#abc7cd")
        draw.text(
            (972, y + 39),
            fit_text(texts.card_points(score), font(30), 245),
            font=font(30),
            fill=rank_color,
            anchor="ra",
        )
    if not rows:
        draw.text(
            (92, top + 36), fit_text(texts.NO_SCORES, font(30), 880), font=font(30), fill="#abc7cd"
        )
    footer = size[1] - (210 if story else 119)
    draw.line((90, footer - 25, 990, footer - 25), fill="#294652", width=2)
    draw.ellipse((91, footer + 8, 117, footer + 34), outline=accent, width=5)
    draw.line((111, footer + 28, 126, footer + 43), fill=accent, width=5)
    draw.text((142, footer), texts.CARD_BRAND, font=font(28), fill="#abc7cd")
    face = font(42 if story else 28)
    draw.text(
        (990, footer + (65 if story else 0)),
        fit_text(texts.card_watermark(instagram), face, 790 if story else 600),
        font=face,
        fill=accent,
        anchor="ra",
    )
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
