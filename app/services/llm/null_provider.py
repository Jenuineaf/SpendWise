from app.services.llm.base import LLMProvider


class NullProvider(LLMProvider):
    """Used when no LLM API key is configured. Returns the grounded data
    summary itself instead of failing, so the endpoint stays useful without a
    key — the honest answer is "here's your data" rather than an error.
    """

    async def ask(self, system_prompt: str, user_question: str) -> str:
        return (
            "No LLM provider is configured (set OPENAI_API_KEY or GEMINI_API_KEY in .env). "
            "Here is the spending summary that would have been analyzed:\n\n" + system_prompt
        )
