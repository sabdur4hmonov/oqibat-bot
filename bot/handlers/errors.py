import logging

from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def handle_error(event: ErrorEvent, error_alerts=None) -> bool:
    error = event.exception
    logger.error(
        "Unhandled error processing update %s",
        event.update.update_id,
        exc_info=(type(error), error, error.__traceback__),
    )
    if error_alerts:
        update = event.update
        container = (
            update.message
            or (update.callback_query.message if update.callback_query else None)
            or update.chat_member
            or update.my_chat_member
        )
        try:
            error_alerts.record(
                error, "handler", getattr(getattr(container, "chat", None), "id", None)
            )
        except Exception:
            logger.warning("Handler error summary could not be recorded")
    return True
