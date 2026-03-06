# capabilities/pre/graph_context.py

from capabilities.base import PreLLMCapability

class GraphContextCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.graph = runtime.graph

    async def process(self, event, context):
        node = event.get("node")

        neighbors = await self.graph.get_neighbors(node)

        context["graph_context"] = {
            "node": node,
            "neighbors": neighbors
        }

        return context