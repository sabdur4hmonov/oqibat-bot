import logging

from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def handle_error(event: ErrorEvent) -> bool:
    error = event.exception
    logger.error(
        "Unhandled error processing update %s",
        event.update.update_id,
        exc_info=(type(error), error, error.__traceback__),
    )
    return True
