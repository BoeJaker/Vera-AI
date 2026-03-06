# capabilities/pre/semantic_retrieval.py
import numpy as np

class SemanticRetrievalCapability:
    def __init__(self, runtime):
        self.store = runtime.context_store
        self.embedding_memory = []

    async def retrieve(self, query_embedding, top_k=5):
        sims = [(i, np.dot(query_embedding, m["embedding"])) for i, m in enumerate(self.embedding_memory)]
        sims.sort(key=lambda x: x[1], reverse=True)
        return [self.embedding_memory[i] for i, _ in sims[:top_k]]

    async def add_note(self, embedding, note):
        self.embedding_memory.append({"embedding": embedding, "note": note})