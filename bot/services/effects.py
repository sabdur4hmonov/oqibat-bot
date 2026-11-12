"""Tracked outbound side effects never hold a scheduler deadline loop open."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class Effects:
    def __init__(self) -> None:
        self.tasks: set[asyncio.Task] = set()
        self.on_error = None

    def start(self, operation) -> None:
        task = asyncio.create_task(operation)
        self.tasks.add(task)
        task.add_done_callback(self._done)

    def _done(self, task) -> None:
        self.tasks.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            logger.error(
                "Background game/challenge notification failed",
                exc_info=(type(error), error, error.__traceback__),
            )
            if self.on_error:
                try:
                    self.on_error(error, "background")
                except Exception:
                    logger.warning("Background error summary could not be recorded")

    async def drain(self) -> None:
        while self.tasks:
            await asyncio.gather(*list(self.tasks))

    async def close(self) -> None:
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
