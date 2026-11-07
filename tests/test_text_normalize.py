import pytest

from bot.utils.text_normalize import normalize_text


@pytest.mark.parametrize(
    "text",
    [
        "O‘zbekiston",
        "Oʻzbekiston",
        "Oʼzbekiston",
        "O‘zBEKIston",
        "O'zbekiston",
        "Ўзбекистон",
        "Ozbekiston",
        "O`zbekiston",
        "O‘zbekiston!!!",
    ],
)
def test_uzbekistan_variants_match(text):
    assert normalize_text(text) == "ozbekiston"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("  Salom,\n DUNYO!  ", "salom dunyo"),
        ("Қўшиқ ғоз шаҳар чой ёз юрак янги ҳаво", "qoshiq goz shahar choy yoz yurak yangi havo"),
        ("G‘isht gʻisht g'isht", "gisht gisht gisht"),
        ("", ""),
        ("?! 😀", ""),
    ],
)
def test_normalization(text, expected):
    assert normalize_text(text) == expected
    assert normalize_text(expected) == expected
