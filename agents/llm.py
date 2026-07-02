from __future__ import annotations
import logging
from config.settings import get_settings

logger = logging.getLogger(__name__)
s = get_settings()


def get_llm(temperature: float = 0.0, max_tokens: int = 4096):
    if s.anthropic_api_key and s.anthropic_api_key != "":
        try:
            from langchain_anthropic import ChatAnthropic
            logger.info("Using direct Anthropic API")
            return ChatAnthropic(
                model="claude-sonnet-4-5",
                api_key=s.anthropic_api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error("Anthropic API failed: %s", e)

    logger.warning("Using stub LLM - set ANTHROPIC_API_KEY in config/.env")
    return _StubLLM()


class _Message:
    def __init__(self, content: str):
        self.content = content


class _StubLLM:
    async def ainvoke(self, prompt: str, **kwargs):
        return _Message(f"[STUB LLM] {prompt[:200]}")

    def invoke(self, prompt: str, **kwargs):
        return _Message(f"[STUB] {prompt[:200]}")
