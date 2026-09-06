from functools import lru_cache

from app.ai.providers.base import LLMProvider
from app.core.config import get_settings


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.LLM_PROVIDER == "anthropic":
        from app.ai.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    raise ValueError(f"Proveedor de LLM desconocido: {settings.LLM_PROVIDER}")
