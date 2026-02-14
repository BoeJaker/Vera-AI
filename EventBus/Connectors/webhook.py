import httpx
from Vera.EventBus.Connectors.base import Connector

class WebhookConnector(Connector):
    def __init__(self, url=None):
        self.url = url

    async def handle(self, event):
        if not self.url:
            return
        async with httpx.AsyncClient() as client:
            await client.post(self.url, json=event.model_dump())
