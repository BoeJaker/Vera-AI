# capabilities/pre/corpus_parser.py

from capabilities.base import PreLLMCapability
import hashlib

class CorpusParserCapability(PreLLMCapability):

    async def setup(self, runtime):
        self.chunk_index = runtime.chunk_index  # e.g., Redis or vector DB

    async def process(self, event, context):
        # event: {"corpus": ["file1", "file2"], "corpus_type": "code|text"}
        corpus = event.get("corpus", [])
        corpus_summary = []

        for doc in corpus:
            chunks = self.chunk_document(doc)
            for chunk in chunks:
                chunk_id = hashlib.sha256(chunk.encode()).hexdigest()
                # Store embeddings or summaries in Redis / vector DB
                await self.chunk_index.store(chunk_id, chunk)
            # Summarize corpus at chunk level
            corpus_summary.append(f"{len(chunks)} chunks processed")
        
        context["corpus_summary"] = corpus_summary
        return context

    def chunk_document(self, doc, size=500):
        # Simple line-based chunking
        lines = doc.splitlines()
        return ["\n".join(lines[i:i+size]) for i in range(0, len(lines), size)]