# capabilities/pre/graph_updater.py

from capabilities.base import PreLLMCapability

class GraphUpdaterCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.graph = runtime.graph

    async def process(self, event, context):
        if context.get("novel") and context.get("normalized_event"):
            node = context["normalized_event"]["entities"][0] if context["normalized_event"]["entities"] else "unknown"
            await self.graph.add_node(node, context)
        return context