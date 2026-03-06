# capabilities/pre/risk_fusion.py

from capabilities.base import PreLLMCapability

class RiskFusionCapability(PreLLMCapability):

    async def process(self, event, context):
        score = 0

        if context.get("anomaly"):
            score += 3

        if len(context.get("graph_context", {}).get("neighbors", [])) > 5:
            score += 2

        context["risk_score"] = score
        context["risk_level"] = (
            "LOW" if score <= 2 else
            "MEDIUM" if score <= 4 else
            "HIGH"
        )

        return context