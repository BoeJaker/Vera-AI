# capabilities/pre/internal_monologue.py
from capabilities.base import PreLLMCapability

class InternalMonologueCapability(PreLLMCapability):
    async def setup(self, runtime):
        self.store = runtime.context_store
        self.key = "internal_monologue"

    async def process(self, event, context):
        # Load current monologue
        monologue = await self.store.load(self.key) or {
            "recent_events": [],
            "novelty_alerts": [],
            "graph_insights": [],
            "code_context": [],
            "hypotheses": [],
            "risks": [],
            "internal_notes": []
        }

        # Add high-value event insights
        if context.get("novel") or context.get("centrality_score",0) > 5:
            monologue["recent_events"].append({
                "event": event,
                "context_summary": context
            })
            monologue["internal_notes"].append(f"Noticing significant activity in {event.get('entities')}")

        # Optionally add drift or risk notes
        if context.get("drift"):
            monologue["internal_notes"].append(f"Metric drift detected: {context.get('drift_stats')}")

        # Save updated monologue
        await self.store.save(self.key, monologue)
        context["internal_monologue"] = monologue
        return context