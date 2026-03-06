# capabilities/pre/blast_radius.py

class BlastRadiusCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.driver = runtime.graph.driver

    async def process(self, event, context):
        node = event.get("node")

        query = """
        MATCH path = (n {name:$node})-[:DEPENDS_ON*1..3]->(m)
        RETURN distinct m.name as impacted
        """

        impacted = []

        async with self.driver.session() as session:
            result = await session.run(query, node=node)
            async for record in result:
                impacted.append(record["impacted"])

        context["blast_radius"] = impacted
        context["blast_radius_size"] = len(impacted)
        return context