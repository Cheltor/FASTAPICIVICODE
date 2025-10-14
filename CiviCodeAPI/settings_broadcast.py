import asyncio
from typing import Set

class Broadcaster:
    def __init__(self):
        self.listeners: Set[asyncio.Queue] = set()

    async def subscribe(self):
        q = asyncio.Queue()
        self.listeners.add(q)
        try:
            while True:
                item = await q.get()
                yield item
        finally:
            self.listeners.discard(q)

    def publish_nowait(self, data):
        for q in list(self.listeners):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

broadcaster = Broadcaster()
