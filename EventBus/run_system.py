# docker run -d -p 6379:6379 redis

import asyncio
from Vera.EventBus.redis_bus import RedisEventBus
from Vera.EventBus.Sensors.test_sensor import test_sensor
from Vera.EventBus.Consumers.anomaly_detector import anomaly_detector
from Vera.EventBus.Connectors.manager import ConnectorManager
from Vera.EventBus.Connectors.console_notifier import ConsoleConnector
from Vera.EventBus.Connectors.slack import SlackConnector
from Vera.EventBus.Connectors.email import EmailConnector
from Vera.EventBus.Connectors.webhook import WebhookConnector

async def main():
    print("🚀 Starting AI Event Bus")

    bus = RedisEventBus("node-1")
    await bus.connect()

    # AI consumers
    bus.subscribe("system.*", anomaly_detector)

    # Connectors
    connectors = ConnectorManager([
        ConsoleConnector(),
        SlackConnector(),    # add webhook later
        EmailConnector(),    # add creds later
        WebhookConnector()   # add URL later
    ])

    async def connector_dispatch(event):
        if event.type.startswith("ai.") or event.type.startswith("system."):
            await connectors.dispatch(event)

    bus.subscribe("*", connector_dispatch)

    asyncio.create_task(test_sensor(bus))

    print("System running...")
    await bus.start()

asyncio.run(main())
