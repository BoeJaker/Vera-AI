# capabilities/post/code_editor.py

from capabilities.base import PostLLMCapability

class CodeEditorCapability(PostLLMCapability):

    async def process(self, llm_output, context):
        if "edit_code" in context:
            code = context["edit_code"]
            # Apply edits suggested by LLM
            context["code_edited"] = code.replace("TODO", "Implemented")
        return context