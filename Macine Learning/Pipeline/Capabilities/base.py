from abc import ABC, abstractmethod

class PreLLMCapability(ABC):
    async def setup(self, runtime): pass

    @abstractmethod
    async def process(self, event: dict, context: dict) -> dict:
        pass


class PostLLMCapability(ABC):
    async def setup(self, runtime): pass

    @abstractmethod
    async def process(self, llm_output: str, context: dict) -> dict:
        pass