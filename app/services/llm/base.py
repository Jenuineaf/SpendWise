from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def ask(self, system_prompt: str, user_question: str) -> str: ...
