# capabilities/post/action_executor.py

class ActionExecutor(PostLLMCapability):

    async def process(self, llm_output, context):

        if context.get("risk_level") == "HIGH":
            print("Triggering mitigation workflow...")
            # call external API
            context["action_executed"] = True

        return context