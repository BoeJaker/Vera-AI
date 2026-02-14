import asyncio, json
import redis.asyncio as redis
from Vera.EventBus.config import *

async def retry_dead_letters():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    while True:
        msgs = await r.xread({STREAM_DLQ: "0"}, count=10, block=5000)
        if not msgs:
            continue
        for _, items in msgs:
            for msg_id, data in items:
                await r.xadd(STREAM_EVENTS, {"event": data["event"]})
                await r.xdel(STREAM_DLQ, msg_id)
                print("♻ Replayed DLQ event")

asyncio.run(retry_dead_letters())
