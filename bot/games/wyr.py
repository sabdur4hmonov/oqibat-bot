"""Pure validation for would-you-rather content."""


def options(item: dict) -> list[str]:
    choices = item["options"]
    if len(choices) != 2 or len(set(choices)) != 2:
        raise ValueError("Would-you-rather requires two distinct options")
    return list(choices)
