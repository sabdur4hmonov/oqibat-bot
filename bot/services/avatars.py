"""Short-lived, bounded public-avatar cache; image bytes keyed by Telegram file_id."""

import asyncio
import base64
import time
from collections import OrderedDict
from io import BytesIO

from aiogram.exceptions import TelegramRetryAfter
from PIL import Image, ImageOps

MAX_AVATAR_BYTES = 256_000


class AvatarBytes(BytesIO):
    def write(self, data):
        if self.tell() + len(data) > MAX_AVATAR_BYTES:
            raise ValueError("Avatar size limit")
        return super().write(data)


def thumbnail(payload):
    with Image.open(BytesIO(payload)) as image:
        if image.width * image.height > 4_000_000:
            return None
        result = ImageOps.fit(image.convert("RGB"), (128, 128))
    output = BytesIO()
    result.info.clear()
    result.save(output, "PNG")
    return output.getvalue()


class Avatars:
    def __init__(self, bot, sender, *, clock=time.monotonic):
        self.bot, self.sender, self.clock = bot, sender, clock
        self.users, self.files, self.pending = OrderedDict(), OrderedDict(), {}
        self.slots = asyncio.Semaphore(2)
        self.deleted = set()

    def forget(self, user):
        self.deleted.add(user)
        entry = self.users.pop(user, None)
        if entry:
            self.files.pop(entry[1], None)
        task = self.pending.pop(user, None)
        if task:
            task.cancel()

    def allow(self, user):
        self.deleted.discard(user)

    async def get(self, user):
        if not user or user <= 0 or user in self.deleted:
            return None
        entry = self.users.get(user)
        if entry and entry[0] > self.clock():
            self.users.move_to_end(user)
            if entry[1] is None:
                return None
            if entry[1] in self.files:
                self.files.move_to_end(entry[1])
                return self.files[entry[1]]
        if user not in self.pending:
            if len(self.pending) >= 64:
                return None  # Optional decoration must not create an unbounded HTTP backlog.
            self.pending[user] = asyncio.create_task(self._fetch(user))
            self.pending[user].add_done_callback(lambda task: self._done(user, task))
        task = self.pending[user]
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if user in self.deleted:
                return None
            raise
        finally:
            if task.done() and self.pending.get(user) is task:
                self.pending.pop(user, None)

    def _done(self, user, task):
        # A cancelled HTTP/card caller can leave a shielded fetch running. Reap it
        # even if that caller never comes back; completed tasks retain image bytes.
        if self.pending.get(user) is task:
            self.pending.pop(user, None)

    async def _fetch(self, user):
        file_id, payload = None, None
        try:
            async with self.slots, asyncio.timeout(4):
                photos = await self.bot.get_user_profile_photos(user_id=user, limit=1)
                if photos.photos:
                    photo = photos.photos[0][0]
                    if (photo.file_size or 0) <= MAX_AVATAR_BYTES:
                        file_id = photo.file_id
                        payload = self.files.get(file_id)
                        if payload is None:
                            stream = AvatarBytes()
                            await self.bot.download(photo, destination=stream, timeout=3)
                            if stream.getbuffer().nbytes <= MAX_AVATAR_BYTES:
                                payload = await asyncio.to_thread(thumbnail, stream.getvalue())
        except TelegramRetryAfter as error:
            self.sender.limiter.pause(None, self.sender.clock.now() + error.retry_after)
            self.sender._wake.set()
        except Exception:
            pass  # Optional decoration; never log raw URLs/tokens or fail a result.
        if user in self.deleted:
            return None
        self.users[user] = (self.clock() + 600, file_id if payload else None)
        if len(self.users) > 20_000:
            self.users.popitem(last=False)
        if file_id and payload:
            self.files[file_id] = payload
            self.files.move_to_end(file_id)
            if len(self.files) > 256:
                self.files.popitem(last=False)
        return payload

    async def encoded(self, user):
        try:
            async with asyncio.timeout(2):
                payload = await self.get(user)
            return (
                "data:image/png;base64," + base64.b64encode(payload).decode() if payload else None
            )
        except TimeoutError:
            return None

    async def close(self):
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.pending.clear()
        self.users.clear()
        self.files.clear()
