# capabilities/pre/centrality.py

from capabilities.base import PreLLMCapability

class GraphCentralityCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.driver = runtime.graph.driver

    async def process(self, event, context):
        node = event.get("node")

        query = """
        MATCH (n {name:$node})-[r]-()
        RETURN count(r) as degree
        """

        async with self.driver.session() as session:
            result = await session.run(query, node=node)
            record = await result.single()
            degree = record["degree"] if record else 0

        context["centrality_score"] = degree
        return context