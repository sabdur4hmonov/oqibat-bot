import asyncio
from collections import deque
from datetime import timedelta
from unittest.mock import patch

import pytest
from aiogram import Bot
from aiogram.methods import EditMessageText, SendDice, SendMessage, SendPoll, StopPoll
from aiogram.types import Message, Poll, PollAnswer, Update
from sqlalchemy import func, select
from test_challenge_flows import command_update
from test_group_flows import GroupTelegram, bot_update, callback, tg_user
from test_private_and_startup import TOKEN

from bot import texts
from bot.__main__ import create_dispatcher
from bot.db.models import GameSession, PointEvent
from bot.db.repo.games import GameBusy
from bot.games import dice_duel, quiz, wyr
from bot.services.runtime import ScaleMiddleware, ScaleRuntime
from bot.utils.time import utc_now


class GameTelegram(GroupTelegram):
    def __init__(self):
        super().__init__()
        self.rolls = deque([6, 1])
        self.polls = {}
        self.sequence = 200

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, (SendDice, SendPoll, StopPoll)):
            self.methods.append(method)
            self.sequence += 1
            if isinstance(method, StopPoll):
                return self.polls[method.message_id]
            payload = {
                "message_id": self.sequence,
                "date": utc_now(),
                "chat": {"id": method.chat_id, "type": "supergroup"},
            }
            if isinstance(method, SendDice):
                payload["dice"] = {"emoji": method.emoji, "value": self.rolls.popleft()}
            else:
                poll = Poll(
                    id=f"poll{self.sequence}",
                    question=method.question,
                    options=[
                        {
                            "text": option if isinstance(option, str) else option.text,
                            "voter_count": 0,
                            "persistent_id": str(i),
                        }
                        for i, option in enumerate(method.options)
                    ],
                    total_voter_count=0,
                    is_closed=False,
                    is_anonymous=method.is_anonymous,
                    type=method.type,
                    allows_multiple_answers=False,
                    allows_revoting=False,
                    members_only=False,
                )
                self.polls[self.sequence] = poll
                payload["poll"] = poll
            return Message.model_validate(payload)
        return await super().make_request(bot, method, timeout)


@pytest.fixture
async def game_app(sessions, settings, fake_clock):
    transport = GameTelegram()
    async with Bot(TOKEN, session=transport) as bot:
        async with ScaleRuntime(sessions, bot, settings) as runtime:
            # Deterministic explicit ticks in game tests; no real waiting or Telegram traffic.
            for task in runtime.tasks:
                task.cancel()
            await asyncio.gather(*runtime.tasks, return_exceptions=True)
            runtime.sender.clock = fake_clock
            dispatcher = create_dispatcher()
            dispatcher.update.outer_middleware(ScaleMiddleware(runtime))

            async def feed(update):
                return await dispatcher.feed_update(
                    bot, update, settings=settings, sessions=sessions, **runtime.workflow()
                )

            await feed(bot_update("administrator"))
            for user in (1, 2, 3, 42):
                await runtime.groups.membership(-1, tg_user(user), opted_in=True)
            yield feed, transport, runtime


def test_dice_ranges_ties_and_winners():
    for emoji in dice_duel.EMOJIS:
        assert dice_duel.winner(emoji, [42, 77], [6, 1]) == 42
        assert dice_duel.winner(emoji, [42, 77], [1, 6]) == 77
        assert dice_duel.winner(emoji, [42, 77], [2, 2]) is None
        for value in (0, 7, True):
            with pytest.raises(ValueError):
                dice_duel.validate_roll(emoji, value)
    with pytest.raises(ValueError):
        dice_duel.winner("⚽", [1, 2], [1, 2])


def test_quiz_first_correct_wrong_and_duplicate_are_pure():
    state = {"phase": "question", "correct": 1}
    first, points = quiz.answer(state, 1, "<User>", [1])
    assert points == 5 and state == {"phase": "question", "correct": 1}
    second, points = quiz.answer(first, 2, "User2", [1])
    assert points == 3
    assert quiz.answer(second, 1, "User", [1])[1] == 0
    assert quiz.answer(second, 3, "User3", [0])[1] == 0
    assert wyr.options({"options": ["A", "B"]}) == ["A", "B"]
    with pytest.raises(ValueError):
        wyr.options({"options": ["A", "A"]})


async def test_open_duel_emoji_choice_tie_reroll_four_seconds_and_one_award(game_app, sessions):
    feed, transport, runtime = game_app
    transport.rolls = deque([3, 3, 6, 1])
    await feed(command_update("/duel"))
    game = runtime.game_cache.for_chat(-1)[0]
    await feed(callback(f"dg:{game.id}:1", 1))
    await feed(callback(f"da:{game.id}", 2))
    await runtime.effects.drain()
    game = runtime.game_cache.get(game.id)
    assert game.state["emoji"] == "🎯" and game.state["phase"] == "animation"
    assert not await runtime.game_hub.advance(game, game.phase_deadline_at - timedelta(seconds=1))
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    game = runtime.game_cache.get(game.id)
    assert game.state["round"] == 2
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    assert runtime.game_cache.get(game.id) is None
    async with sessions() as session:
        assert (await session.get(GameSession, game.id)).status == "finished"
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 2
        assert (await session.scalars(select(PointEvent))).one().user_id == 1
    assert len([m for m in transport.methods if isinstance(m, SendDice)]) == 4
    assert "&lt;Sinov&gt;" in transport.methods[-1].text


async def test_reply_duel_only_target_can_accept_and_button_spam_is_serialized(game_app):
    feed, transport, runtime = game_app
    update = command_update("/duel")
    reply = command_update("Hi", 5, 2).message
    await feed(
        update.model_copy(
            update={"message": update.message.model_copy(update={"reply_to_message": reply})}
        )
    )
    game = runtime.game_cache.for_chat(-1)[0]
    await feed(callback(f"da:{game.id}", 3))
    assert runtime.game_cache.get(game.id).state["phase"] == "lobby"
    await asyncio.gather(*[feed(callback(f"da:{game.id}", 2)) for _ in range(5)])
    await runtime.effects.drain()
    assert len([m for m in transport.methods if isinstance(m, SendDice)]) == 2


async def test_quiz_five_polls_scores_answers_and_edits_one_final_board(game_app, sessions):
    feed, transport, runtime = game_app
    await feed(command_update("/viktorina"))
    for question in range(5):
        game = runtime.game_cache.main(-1)
        assert game.state["question_index"] == question
        correct = game.state["correct"]

        async def answer(user, choice, poll_id=game.state["poll_id"]):
            await feed(
                Update(
                    update_id=300 + user,
                    poll_answer=PollAnswer(
                        poll_id=poll_id,
                        user=tg_user(user),
                        option_ids=[choice],
                        option_persistent_ids=[str(choice)],
                    ),
                )
            )

        await asyncio.gather(answer(1, correct), answer(2, correct))
        await answer(1, correct)
        await answer(77, correct)  # no consent
        game = runtime.game_cache.main(-1)
        await runtime.game_hub.advance(game, game.phase_deadline_at)
        await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None
    polls = [m for m in transport.methods if isinstance(m, SendPoll)]
    assert len(polls) == 5
    assert all(not p.is_anonymous and p.type == "quiz" and p.open_period == 30 for p in polls)
    assert all(p.correct_option_ids and p.allows_revoting is False for p in polls)
    assert len([m for m in transport.methods if isinstance(m, SendMessage)]) == 2
    edits = [m for m in transport.methods if isinstance(m, EditMessageText)]
    assert all(m.message_id == 100 for m in edits)
    assert "yakunlandi" in edits[-1].text and "&lt;Sinov&gt;" in edits[-1].text
    async with sessions() as session:
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 40
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 10


async def test_wyr_regular_nonanonymous_stop_authorization_and_anonymous_admin(game_app):
    feed, transport, runtime = game_app
    await feed(command_update("/tanla"))
    poll = next(m for m in transport.methods if isinstance(m, SendPoll))
    assert poll.type == "regular" and not poll.is_anonymous
    await feed(command_update("/stop", 112, 3))
    assert transport.methods[-1].text == texts.STOP_DENIED
    assert runtime.game_cache.main(-1)
    update = command_update("/stop", 113, 108)
    await feed(
        update.model_copy(
            update={
                "message": update.message.model_copy(
                    update={"from_user": tg_user(108, True), "sender_chat": update.message.chat}
                )
            }
        )
    )
    assert runtime.game_cache.main(-1) is None
    assert any(isinstance(m, StopPoll) for m in transport.methods)


async def test_game_deadline_commits_during_global_outbound_pause(game_app, sessions):
    feed, transport, runtime = game_app
    await feed(command_update("/tanla"))
    game = runtime.game_cache.main(-1)

    # A non-advancing pause keeps sends waiting while the deadline hook still returns.
    async def paused_sleep(_):
        await asyncio.Event().wait()

    with patch.object(runtime.sender.clock, "sleep", new=paused_sleep):
        runtime.sender.limiter.pause(None, runtime.sender.clock.now() + 3600)
        await asyncio.wait_for(runtime.game_hub.advance(game, game.phase_deadline_at), 2)
        async with sessions() as session:
            assert (await session.get(GameSession, game.id)).status == "finished"
        assert runtime.effects.tasks


async def test_main_game_creation_race_and_restart_cancels_ambiguous_send(game_app):
    feed, transport, runtime = game_app
    results = await asyncio.gather(
        *[
            runtime.games.start(
                -1, 1, "quiz", {"phase": "sending"}, utc_now() + timedelta(seconds=90)
            )
            for _ in range(2)
        ],
        return_exceptions=True,
    )
    assert sum(isinstance(result, GameBusy) for result in results) == 1
    game = runtime.game_cache.main(-1)
    await runtime.game_hub.recover([game])
    assert runtime.game_cache.main(-1) is None
    await runtime.effects.drain()


async def test_instant_poll_answer_before_send_response_is_scored(game_app):
    feed, transport, runtime = game_app
    original = transport.make_request

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        sent = await original(bot, method, timeout)
        if isinstance(method, SendPoll):
            choice = method.correct_option_ids[0]
            await runtime.easy_games.answer(
                PollAnswer(
                    poll_id=sent.poll.id,
                    user=tg_user(1),
                    option_ids=[choice],
                    option_persistent_ids=[str(choice)],
                )
            )
        return sent

    with patch.object(transport, "make_request", side_effect=request):
        await feed(command_update("/viktorina"))
    assert (await runtime.points.stats(-1, 1))[0] == 5
    assert not runtime.easy_games.early_answers


async def test_stopping_duel_before_animation_deadline_prevents_award(game_app, sessions):
    feed, transport, runtime = game_app
    await feed(command_update("/duel"))
    game = runtime.game_cache.for_chat(-1)[0]
    await feed(callback(f"da:{game.id}", 2))
    await runtime.effects.drain()
    game = runtime.game_cache.get(game.id)
    await feed(command_update("/stop"))
    assert not await runtime.game_hub.advance(game, game.phase_deadline_at)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0
