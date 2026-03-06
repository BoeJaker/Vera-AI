# context_store.py

import redis.asyncio as redis
import json

class ContextStore:

    def __init__(self, url):
        self.redis = redis.from_url(url)

    async def save(self, key, context):
        await self.redis.set(key, json.dumps(context))

    async def load(self, key):
        data = await self.redis.get(key)
        return json.loads(data) if data else {}