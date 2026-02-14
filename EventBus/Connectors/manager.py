class ConnectorManager:
    def __init__(self, connectors):
        self.connectors = connectors

    async def dispatch(self, event):
        for c in self.connectors:
            await c.handle(event)
