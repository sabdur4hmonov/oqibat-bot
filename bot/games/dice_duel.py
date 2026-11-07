"""Pure dice validation/resolution; never trust user-sent or forwarded dice."""

EMOJIS = ("🎲", "🎯", "🎳")


def validate_roll(emoji: str, value: int) -> None:
    if emoji not in EMOJIS or type(value) is not int or not 1 <= value <= 6:
        raise ValueError("Invalid dice result")


def winner(emoji: str, players: list[int], rolls: list[int]) -> int | None:
    if len(players) != 2 or len(set(players)) != 2 or len(rolls) != 2:
        raise ValueError("Duel requires two distinct players")
    for roll in rolls:
        validate_roll(emoji, roll)
    return None if rolls[0] == rolls[1] else players[0 if rolls[0] > rolls[1] else 1]
