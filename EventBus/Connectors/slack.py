import httpx
from Vera.EventBus.Connectors.base import Connector

class SlackConnector(Connector):
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url

    async def handle(self, event):
        if not self.webhook_url:
            return
        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json={
                "text": f"{event.type}\n{event.payload}"
            })
