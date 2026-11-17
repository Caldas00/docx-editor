"""Chat model factory."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from ..config import Settings, get_settings

_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5", "gpt-6")


def is_reasoning_model(model: str) -> bool:
    return model.startswith(_REASONING_PREFIXES) and "chat" not in model


def make_llm(settings: Settings | None = None, model: str | None = None) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    settings = settings or get_settings()
    name = model or settings.model
    kwargs: dict = {"model": name, "timeout": settings.request_timeout, "max_retries": 2}
    if is_reasoning_model(name):
        # Reasoning models only accept function tools together with reasoning on the
        # Responses API.
        kwargs["use_responses_api"] = True
        kwargs["reasoning"] = {"effort": settings.reasoning_effort}
    else:
        kwargs["temperature"] = 0
    return ChatOpenAI(**kwargs)
