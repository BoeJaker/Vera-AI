import asyncio, json, fnmatch
import redis.asyncio as redis
from Vera.EventBus.event_model import Event
from Vera.EventBus.config import *

class RedisEventBus:
    def __init__(self, consumer_name: str):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)
        self.consumer = consumer_name
        self.subscribers = {}

    async def connect(self):
        await self._create_group(STREAM_EVENTS)
        await self._create_group(STREAM_PRIORITY)

    async def _create_group(self, stream):
        try:
            await self.redis.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        except redis.ResponseError:
            pass

    def subscribe(self, topic_pattern, handler):
        self.subscribers.setdefault(topic_pattern, []).append(handler)

    async def publish(self, event: Event, priority=False):
        stream = STREAM_PRIORITY if priority else STREAM_EVENTS
        await self.redis.xadd(stream, {"event": event.model_dump_json()})

    async def start(self):
        while True:
            await self._consume_stream(STREAM_PRIORITY)
            await self._consume_stream(STREAM_EVENTS)

    async def _consume_stream(self, stream):
        response = await self.redis.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=self.consumer,
            streams={stream: ">"},
            count=10,
            block=3000
        )

        if not response:
            return

        for _, messages in response:
            for message_id, data in messages:
                event = Event.model_validate_json(data["event"])
                try:
                    await self._dispatch(event)
                    await self.redis.xack(stream, CONSUMER_GROUP, message_id)
                except Exception as e:
                    await self._handle_failure(event, e)

    async def _dispatch(self, event):
        tasks = []
        for pattern, handlers in self.subscribers.items():
            if fnmatch.fnmatch(event.type, pattern):
                for h in handlers:
                    tasks.append(asyncio.create_task(h(event)))
        if tasks:
            await asyncio.gather(*tasks)

    async def _handle_failure(self, event, error):
        event.retries += 1
        event.meta["last_error"] = str(error)

        if event.retries >= MAX_RETRIES:
            print("💀 DLQ:", event.type)
            await self.redis.xadd(STREAM_DLQ, {"event": event.model_dump_json()})
        else:
            print("🔁 Retry:", event.type)
            await asyncio.sleep(RETRY_DELAY_SEC)
            await self.publish(event)
