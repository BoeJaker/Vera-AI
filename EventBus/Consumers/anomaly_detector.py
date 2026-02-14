from Vera.EventBus.event_model import Event

async def anomaly_detector(event: Event):
    if event.type == "system.cpu.high":
        if event.payload["cpu"] > 85:
            print("🔥 CRITICAL CPU")
