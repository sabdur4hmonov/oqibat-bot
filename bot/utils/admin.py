"""Pure Telegram membership predicates and cached permission checks."""


def member_is_active(member) -> bool:
    return member.status in {"creator", "administrator", "member"} or (
        member.status == "restricted" and member.is_member
    )


def member_is_admin(member) -> bool:
    return member.status in {"creator", "administrator"}


async def is_admin(admins, chat_id: int, user_id: int) -> bool:
    return user_id in await admins.get(chat_id)
