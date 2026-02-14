import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Any
import fnmatch

EVENT_LOG = Path("event_log.jsonl")

class Event:
    def __init__(self, type: str, source: str, payload: dict, meta: dict | None = None):
        self.id = str(uuid.uuid4())
        self.type = type
        self.source = source
        self.timestamp = datetime.utcnow().isoformat()
        self.payload = payload
        self.meta = meta or {}

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_dict(d):
        e = Event(d["type"], d["source"], d["payload"], d["meta"])
        e.id = d["id"]
        e.timestamp = d["timestamp"]
        return e


class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.queue = asyncio.Queue()

    # --------------------
    # Publishing
    # --------------------
    async def publish(self, event: Event):
        await self.queue.put(event)
        await self._persist(event)

    async def _persist(self, event: Event):
        with EVENT_LOG.open("a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    # --------------------
    # Subscribing
    # --------------------
    def subscribe(self, topic_pattern: str, handler: Callable):
        """
        topic_pattern supports wildcards:
        network.* 
        *.detected
        """
        self.subscribers.setdefault(topic_pattern, []).append(handler)

    # --------------------
    # Event Loop
    # --------------------
    async def start(self):
        while True:
            event = await self.queue.get()
            await self._dispatch(event)

    async def _dispatch(self, event: Event):
        for pattern, handlers in self.subscribers.items():
            if fnmatch.fnmatch(event.type, pattern):
                for handler in handlers:
                    asyncio.create_task(handler(event))

    # --------------------
    # Replay
    # --------------------
    async def replay(self):
        if not EVENT_LOG.exists():
            return
        with EVENT_LOG.open() as f:
            for line in f:
                event = Event.from_dict(json.loads(line))
                await self._dispatch(event)



async def main():
    bus = EventBus()

    # Subscriptions
    bus.subscribe("network.*", anomaly_detector)
    bus.subscribe("*.detected", console_messenger)

    # Start sensors
    asyncio.create_task(packet_sensor(bus))
    asyncio.create_task(cpu_sensor(bus))

    # Start bus loop
    await bus.start()

asyncio.run(main())


"""

async def packet_sensor(bus):
    while True:
        await asyncio.sleep(2)

        await bus.publish(Event(
            type="network.packet.received",
            source="sensor.packet",
            payload={"bytes": 1500, "ip": "10.0.0.5"}
        ))


        import psutil

async def cpu_sensor(bus):
    while True:
        await asyncio.sleep(5)

        cpu = psutil.cpu_percent()

        if cpu > 70:
            await bus.publish(Event(
                type="system.cpu.high",
                source="sensor.cpu",
                payload={"cpu": cpu}
            ))

async def console_messenger(event):
    if event.type.endswith(".detected"):
        print(f"[ALERT] {event.type} -> {event.payload}")


"""