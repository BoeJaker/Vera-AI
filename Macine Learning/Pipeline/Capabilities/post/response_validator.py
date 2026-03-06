# capabilities/post/response_validator.py

from capabilities.base import PostLLMCapability

class ResponseValidator(PostLLMCapability):

    async def process(self, llm_output, context):

        if context.get("risk_level") == "HIGH" and "low risk" in llm_output.lower():
            context["validation_warning"] = "LLM risk mismatch"

        return context