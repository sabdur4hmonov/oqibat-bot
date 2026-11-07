from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from aiogram.methods import AnswerCallbackQuery, SendMessage
from sqlalchemy import func, select
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import bot_update, callback

from bot import texts
from bot.db.models import GameSession, PointEvent
from bot.games import krokodil
from bot.services.content import validate_bank


def state():
    return {
        "phase": "playing",
        "word": "O‘zbekiston",
        "host": 1,
        "round": 1,
        "skips": 0,
        "scores": {},
        "generation": 1,
        "end_at": None,
    }


@pytest.mark.parametrize(
    "word", ["O‘zbekiston", "Oʻzbekiston", "O'zbekiston", "Ўзбекистон", "Ozbekiston!"]
)
def test_matching_normalizes_apostrophes_cyrillic_and_punctuation(word):
    assert krokodil.matches(word, "O‘zbekiston")
    assert not krokodil.matches("O‘zbekiston poytaxti", "O‘zbekiston")
    assert krokodil.reveals("Men O'zbekiston dedim", "O‘zbekiston")
    assert not krokodil.reveals("Mushuklar", "Mushuk")
    assert not krokodil.matches("", "!!!")


def test_pure_guess_skip_timeout_and_tenth_round():
    original = state()
    before = deepcopy(original)
    changed, awards = krokodil.guess(original, 2, "Ўзбекистон")
    assert original == before and awards == [(2, 5), (1, 3)]
    assert changed["host"] == 2 and changed["round"] == 2
    revealed, awards = krokodil.guess(original, 1, "Bu O'zbekiston!")
    assert awards == [(1, -3)] and revealed["round"] == 1
    skipped = krokodil.skip(original, 1)
    assert skipped["skips"] == 1 and original["skips"] == 0
    assert krokodil.skip(original, 2) is None
    assert krokodil.skip({**original, "skips": 2}, 1) is None
    assert krokodil.guess(original, 2, "Mushuk") is None
    last = {**original, "round": 10}
    assert krokodil.guess(last, 2, "Ozbekiston")[0]["phase"] == "done"
    assert krokodil.timeout(last, 3)["phase"] == "done"
    assert krokodil.timeout(original, 3)["host"] == 3
    for invalid in ("!", "A" * 101):
        with pytest.raises(ValueError):
            validate_bank("krokodil_words", [{"key": "test", "word": invalid}])


async def test_word_is_private_target_only_and_two_skips_preserve_round_deadline(game_app):
    feed, transport, runtime = game_app
    await feed(command_update("/krokodil"))
    game = runtime.game_cache.main(-1)
    end = game.phase_deadline_at
    sends = len([m for m in transport.methods if isinstance(m, SendMessage)])
    await feed(callback(f"kw:{game.id}", 2))
    assert transport.methods[-1].text == texts.KROK_HOST_ONLY
    await feed(callback(f"kw:{game.id}", 1))
    answer = transport.methods[-1]
    assert isinstance(answer, AnswerCallbackQuery) and answer.show_alert
    assert game.state["word"] in answer.text
    assert len([m for m in transport.methods if isinstance(m, SendMessage)]) == sends
    for _ in range(2):
        await feed(callback(f"ks:{game.id}", 1))
        await runtime.effects.drain()
    game = runtime.game_cache.main(-1)
    assert game.state["skips"] == 2 and game.phase_deadline_at == end
    await feed(callback(f"ks:{game.id}", 1))
    assert transport.methods[-1].text == texts.KROK_NO_SKIPS


async def test_ten_round_game_three_people_scores_and_next_host(game_app, sessions):
    feed, transport, runtime = game_app
    runtime.content.banks["krokodil_words"] = [{"key": "word_test", "word": "O‘zbekiston"}]
    await feed(command_update("/krokodil"))
    game_id = runtime.game_cache.main(-1).id
    for round_number in range(1, 11):
        game = runtime.game_cache.main(-1)
        assert game.state["round"] == round_number
        guesser = 3 if game.state["host"] == 2 else 2
        await feed(command_update("ЎЗБЕКИСТОН!!!", 500 + round_number, guesser))
        if round_number < 10:
            assert runtime.game_cache.main(-1).state["host"] == guesser
    assert runtime.game_cache.main(-1) is None
    async with sessions() as session:
        assert (await session.get(GameSession, game_id)).status == "finished"
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 80
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 20
    assert "10 tur" in transport.methods[-1].text


async def test_host_reveal_penalty_new_word_and_duplicate_message_rejected(game_app):
    feed, transport, runtime = game_app
    runtime.content.banks["krokodil_words"] = [{"key": "word_test", "word": "O‘zbekiston"}]
    await feed(command_update("/krokodil"))
    update = command_update("Bu Ozbekiston!", 700, 1)
    await feed(update)
    game = runtime.game_cache.main(-1)
    assert game.state["round"] == 1 and game.state["generation"] == 2
    assert (await runtime.points.stats(-1, 1))[0] == -3
    await feed(update)
    assert (await runtime.points.stats(-1, 1))[0] == -3


async def test_timeout_reveals_word_selects_opted_host_and_stop_works(game_app):
    feed, transport, runtime = game_app
    await feed(command_update("/krokodil"))
    game = runtime.game_cache.main(-1)
    word = game.state["word"]
    await runtime.game_hub.advance(game, game.phase_deadline_at + timedelta(seconds=1))
    await runtime.effects.drain()
    next_game = runtime.game_cache.main(-1)
    assert next_game.state["round"] == 2
    assert next_game.state["host"] in runtime.participants.for_chat(-1)
    assert word in transport.methods[-1].text
    await feed(command_update("/stop"))
    assert runtime.game_cache.main(-1) is None


async def test_unrelated_guesses_have_zero_sql_and_nonparticipant_cannot_guess(game_app):
    feed, transport, runtime = game_app
    await feed(command_update("/krokodil"))
    game = runtime.game_cache.main(-1)
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=AssertionError("SQL")):
        await feed(command_update("Bu javob emas", 800, 2))
        await feed(command_update(game.state["word"], 801, 77))
    assert runtime.game_cache.main(-1).state["round"] == 1


async def test_game_cannot_award_after_bot_loses_admin_rights(game_app, sessions):
    feed, transport, runtime = game_app
    await feed(command_update("/krokodil"))
    game = runtime.game_cache.main(-1)
    await feed(bot_update("member", "administrator"))
    await feed(command_update(game.state["word"], 900, 2))
    assert runtime.game_cache.main(-1) is None
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0
