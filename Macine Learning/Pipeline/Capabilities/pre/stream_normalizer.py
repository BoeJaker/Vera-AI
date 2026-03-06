# capabilities/pre/stream_normalizer.py

from capabilities.base import PreLLMCapability

class StreamNormalizerCapability(PreLLMCapability):

    async def process(self, event, context):
        # standardize fields
        normalized = {
            "timestamp": event.get("timestamp"),
            "domain": event.get("domain"),
            "entities": event.get("entities", []),
            "geo": event.get("geo"),
            "numeric_features": event.get("numeric_features", {}),
            "text": event.get("text", ""),
            "source_weight": event.get("source_weight", 1.0)
        }
        context["normalized_event"] = normalized
        return context