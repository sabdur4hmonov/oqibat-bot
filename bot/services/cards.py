"""Deterministic Pillow cards with a bundled, licensed Uzbek-capable font."""

import unicodedata
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bot import texts

FONT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "NotoSans.ttf"
SIZE = (1000, 820)


def plain_line(value):
    # Draw text as pixels, never HTML. Remove controls/bidi overrides and bound work.
    return " ".join(
        "".join(
            char for char in str(value)[:512] if not unicodedata.category(char).startswith("C")
        ).split()
    )


def fit_text(value, font, width):
    value = plain_line(value)
    if font.getlength(value) <= width:
        return value
    low, high = 0, len(value)
    while low < high:
        middle = (low + high + 1) // 2
        if font.getlength(value[:middle] + "…") <= width:
            low = middle
        else:
            high = middle - 1
    return value[:low] + "…"


def render_card(title, rows, instagram, subtitle=None) -> bytes:
    image = Image.new("RGB", SIZE, "#0b1d29")
    draw = ImageDraw.Draw(image)
    draw.ellipse((710, -200, 1260, 350), fill="#113b43")
    draw.ellipse((-280, 560, 280, 1120), fill="#102e3d")
    draw.rounded_rectangle((54, 54, 68, 150), radius=7, fill="#48dcc0")
    heading = ImageFont.truetype(str(FONT), 46)
    body = ImageFont.truetype(str(FONT), 31)
    small = ImageFont.truetype(str(FONT), 24)
    score_font = ImageFont.truetype(str(FONT), 29)
    draw.text((94, 59), fit_text(title, heading, 820), font=heading, fill="#f7f1e8")
    draw.text((96, 126), fit_text(subtitle or texts.SLOGAN, small, 800), font=small, fill="#a8c6ca")
    for rank, (name, score) in enumerate(rows[:5], 1):
        top = 205 + (rank - 1) * 99
        draw.rounded_rectangle((58, top, 942, top + 82), radius=18, fill="#173443")
        draw.text((85, top + 21), str(rank), font=body, fill="#48dcc0")
        score_label = texts.card_points(score)
        score_width = min(score_font.getlength(score_label), 260)
        name_width = 730 - score_width
        draw.text((144, top + 21), fit_text(name, body, name_width), font=body, fill="#f7f1e8")
        draw.text(
            (911, top + 23),
            fit_text(score_label, score_font, 260),
            font=score_font,
            fill="#48dcc0",
            anchor="ra",
        )
    if not rows:
        draw.rounded_rectangle((58, 205, 942, 287), radius=18, fill="#173443")
        draw.text((95, 227), texts.NO_SCORES, font=body, fill="#f7f1e8")
    draw.line((59, 746, 941, 746), fill="#2f505b", width=2)
    draw.text((60, 766), texts.CARD_BRAND, font=small, fill="#a8c6ca")
    draw.text(
        (940, 766),
        fit_text(texts.card_watermark(instagram), small, 580),
        font=small,
        fill="#48dcc0",
        anchor="ra",
    )
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
