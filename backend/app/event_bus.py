# backend/event_bus.py

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from typing import List


class EventBus:
    def __init__(self):
        self.subscribers: set[asyncio.Queue] = set()
        self.history = deque(maxlen=300)

    def publish(self, event_type: str, payload: dict):
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "payload": payload,
        }

        self.history.append(event)

        dead_subscribers = []

        for queue in self.subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead_subscribers.append(queue)

        for queue in dead_subscribers:
            self.subscribers.discard(queue)

    async def subscribe(self):
        queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(queue)

        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self.subscribers.discard(queue)

    def get_recent(self, limit: int = 50) -> List[dict]:
        limit = max(1, int(limit))
        return list(self.history)[-limit:]


event_bus = EventBus()