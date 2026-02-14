from Vera.EventBus.Connectors.base import Connector

class ConsoleConnector(Connector):
    async def handle(self, event):
        print(f"📣 {event.type} -> {event.payload}")
