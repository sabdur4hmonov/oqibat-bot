"""Generate synthetic, reviewable previews without .env, Telegram or database access."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot import texts  # noqa: E402
from bot.services.cards import render_card  # noqa: E402


def main():
    directory = ROOT / "docs/design"
    directory.mkdir(exist_ok=True)
    rows = [(name, 150 - index * 23) for index, name in enumerate(texts.CARD_PREVIEW_NAMES)]
    styles = {kind: f"{emoji} {name}" for kind, (emoji, name, _) in texts.GAME_STYLE.items()}
    styles.update(weekly=texts.CARD_WEEKLY_TITLE, season=texts.SEASON_TITLE)
    for kind, title in styles.items():
        for story in (False, True):
            name = f"{kind}-{'story' if story else 'square'}.png"
            (directory / name).write_bytes(
                render_card(title, rows, "oqibat.preview", kind=kind, story=story)
            )
            print(name)


if __name__ == "__main__":
    main()
