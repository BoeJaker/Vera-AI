# capabilities/post/monologue_refinement.py
class MonologueRefinementCapability:
    async def process(self, llm_output, context):
        monologue = context.get("internal_monologue", {})
        # Simplified: append LLM summary
        summary = llm_output.get("summary", "No summary")
        monologue["summaries"] = monologue.get("summaries", []) + [summary]
        context["internal_monologue"] = monologue
        return context