# capabilities/post/confidence_estimator.py

from capabilities.base import PostLLMCapability
import random

class ConfidenceEstimator(PostLLMCapability):

    async def process(self, llm_output, context):

        base = 0.6

        if context.get("anomaly"):
            base -= 0.1

        if context.get("risk_level") == "HIGH":
            base += 0.1

        context["llm_confidence"] = round(min(max(base, 0.1), 0.95), 2)

        return context