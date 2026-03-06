import asyncio

from pipeline import CapabilityPipeline
from ollama_client import OllamaClient
from eventbus import EventBus
from graph_adapter import GraphAdapter

from capabilities.pre.anomaly import AnomalyCapability
from capabilities.pre.graph_context import GraphContextCapability
from capabilities.pre.risk_fusion import RiskFusionCapability

from capabilities.post.response_validator import ResponseValidator
from capabilities.post.confidence_estimator import ConfidenceEstimator


class Runtime:
    def __init__(self):
        self.graph = GraphAdapter()


async def main():

    runtime = Runtime()

    llm = OllamaClient(
        endpoint="http://localhost:11434/api/generate",
        model="llama3"
    )

    pipeline = CapabilityPipeline(
        pre_caps=[
            AnomalyCapability(),
            GraphContextCapability(),
            RiskFusionCapability()
        ],
        post_caps=[
            ResponseValidator(),
            ConfidenceEstimator()
        ],
        llm=llm
    )

    await pipeline.initialize(runtime)

    bus = EventBus()

    async def handler(event):
        result = await pipeline.run(event)
        print("FINAL OUTPUT:\n", result)

    bus.subscribe(handler)

    # Simulated event
    await bus.publish({
        "node": "web01",
        "features": [[0.9, 0.1, 0.3, 0.7]]
    })


if __name__ == "__main__":
    asyncio.run(main())