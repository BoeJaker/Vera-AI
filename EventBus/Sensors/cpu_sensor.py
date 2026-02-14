import asyncio, psutil
from Vera.EventBus.event_model import Event

async def cpu_sensor(bus):
    while True:
        await asyncio.sleep(5)
        cpu = psutil.cpu_percent()

        if cpu > 60:
            await bus.publish(Event(
                type="system.cpu.high",
                source="sensor.cpu",
                payload={"cpu": cpu}
            ))
