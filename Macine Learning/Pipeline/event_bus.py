# eventbus.py

class EventBus:

    def __init__(self):
        self.subscribers = []

    def subscribe(self, handler):
        self.subscribers.append(handler)

    async def publish(self, event):
        for sub in self.subscribers:
            await sub(event)