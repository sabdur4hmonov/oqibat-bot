import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger(__name__)


class Metrics:
    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.buckets: deque[list[int]] = deque(maxlen=60)

    def record_update(self) -> None:
        second = int(self.clock())
        if self.buckets and self.buckets[-1][0] == second:
            self.buckets[-1][1] += 1
        else:
            self.buckets.append([second, 1])

    @property
    def updates_per_minute(self) -> int:
        cutoff = int(self.clock()) - 60
        return sum(count for second, count in self.buckets if second > cutoff)

    def log(self, sender, scheduler) -> None:
        logger.info(
            "scale queue_length=%d updates_per_minute=%d last_tick_duration_ms=%.3f",
            sender.queue_length,
            self.updates_per_minute,
            scheduler.last_tick_duration * 1000,
        )

    async def run(self, sender, scheduler) -> None:
        while True:
            await asyncio.sleep(300)
            self.log(sender, scheduler)
