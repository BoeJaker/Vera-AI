import asyncio, random
from Vera.EventBus.event_model import Event

async def test_sensor(bus):
    while True:
        await asyncio.sleep(3)
        cpu = random.randint(10,95)

        await bus.publish(Event(
            type="system.cpu.high",
            source="sensor.test",
            payload={"cpu": cpu}
        ))

        if cpu > 80:
            await bus.publish(Event(
                type="ai.anomaly.detected",
                source="sensor.test",
                payload={"cpu": cpu}
            ), priority=True)
