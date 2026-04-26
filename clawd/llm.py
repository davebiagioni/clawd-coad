from langchain_core.language_models import BaseChatModel

from .config import settings


def make_llm() -> BaseChatModel:
    if settings.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.model,
            api_key=settings.api_key,
            temperature=0,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model,
        base_url=settings.base_url,
        api_key=settings.api_key,
        temperature=0,
    )
