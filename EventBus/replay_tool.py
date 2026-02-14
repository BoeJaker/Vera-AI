import asyncio, redis.asyncio as redis
from Vera.EventBus.config import *

async def replay():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    events = await r.xrange(STREAM_EVENTS, "-", "+")
    for id, data in events:
        print(id, data["event"])

asyncio.run(replay())
