"""Pure normalization foundation for future guessing games."""

import re

_APOSTROPHES = str.maketrans("ʻʼ’‘`'", "''''''")
_CYRILLIC = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "j",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "x",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "i",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ў": "o'",
        "қ": "q",
        "ғ": "g'",
        "ҳ": "h",
    }
)


def normalize_text(text: str) -> str:
    text = text.casefold().translate(_APOSTROPHES).translate(_CYRILLIC).replace("'", "")
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", text).split())
