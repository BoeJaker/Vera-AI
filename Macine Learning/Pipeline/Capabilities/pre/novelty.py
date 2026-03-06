# capabilities/pre/novelty.py

import httpx
import numpy as np

class EmbeddingNoveltyCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.endpoint = "http://ollama:11434/api/embeddings"
        self.memory = []

    async def embed(self, text):
        async with httpx.AsyncClient() as client:
            r = await client.post(self.endpoint, json={
                "model": "llama3",
                "prompt": text
            })
        return np.array(r.json()["embedding"])

    async def process(self, event, context):
        text = event.get("description", "")
        embedding = await self.embed(text)

        if not self.memory:
            self.memory.append(embedding)
            context["novel"] = False
            return context

        sims = [np.dot(embedding, m) for m in self.memory]
        max_sim = max(sims)

        context["novel"] = max_sim < 0.8

        if context["novel"]:
            self.memory.append(embedding)

        return context