# ollama_client.py

import httpx
import json

class OllamaClient:

    def __init__(self, endpoint, model):
        self.endpoint = endpoint
        self.model = model

    async def generate(self, context):

        prompt = f"""
You are a system reasoning engine.

Structured World Context:
{json.dumps(context, indent=2)}

Provide:
1. Situation summary
2. Risk assessment
3. Recommended actions
4. Confidence explanation
"""

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", self.endpoint, json={
                "model": model,
                "prompt": prompt,
                "stream": True
            }) as response:

                async for line in response.aiter_lines():
                    if line:
                        yield json.loads(line)["response"]

