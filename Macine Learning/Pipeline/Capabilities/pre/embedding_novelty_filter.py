# capabilities/pre/embedding_novelty_filter.py

from capabilities.base import PreLLMCapability
import numpy as np

class EmbeddingNoveltyFilter(PreLLMCapability):

    async def setup(self, runtime):
        self.memory_embeddings = []

    async def process(self, event, context):
        # Simplified: embed text
        text = event.get("text") or "no_text"
        embedding = np.random.rand(128)  # Replace with real embedding model
        context["embedding"] = embedding

        if not self.memory_embeddings:
            self.memory_embeddings.append(embedding)
            context["novel"] = True
        else:
            sims = [np.dot(embedding, m) for m in self.memory_embeddings]
            context["novel"] = max(sims) < 0.85
            if context["novel"]:
                self.memory_embeddings.append(embedding)
        return context