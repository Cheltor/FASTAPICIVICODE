import asyncio
from typing import Set

class Broadcaster:
    """
    A simple broadcaster for SSE (Server-Sent Events).

    Attributes:
        listeners (set[asyncio.Queue]): Set of active listener queues.
    """
    def __init__(self):
        self.listeners: Set[asyncio.Queue] = set()

    async def subscribe(self):
        """
        Subscribe to the broadcast stream.

        Yields:
            Any: Items published to the stream.
        """
        q = asyncio.Queue()
        self.listeners.add(q)
        try:
            while True:
                item = await q.get()
                yield item
        finally:
            self.listeners.discard(q)

    def publish_nowait(self, data):
        """
        Publish data to all subscribers without waiting.

        Args:
            data (Any): The data to publish.
        """
        for q in list(self.listeners):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

broadcaster = Broadcaster()
