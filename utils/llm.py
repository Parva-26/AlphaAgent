"""LLM factory and usage accounting helpers."""

from __future__ import annotations

from typing import Any

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult
from langchain_groq import ChatGroq

from .config import LLM_CONFIG
from .cost_tracker import cost_tracker


class CostTrackingCallbackHandler(BaseCallbackHandler):
    """Capture LangChain LLM token usage and forward it to CostTracker."""

    def __init__(self, label: str):
        super().__init__()
        self.label = label

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        input_tokens, output_tokens = extract_usage_from_llm_result(response)
        if input_tokens or output_tokens:
            cost_tracker.add_usage(input_tokens, output_tokens, label=self.label)


def build_groq(
    *,
    temperature: float = LLM_CONFIG.temperature,
    max_tokens: int = LLM_CONFIG.max_tokens,
    callbacks: list[BaseCallbackHandler] | None = None,
) -> ChatGroq:
    """Create the Groq-hosted chat model used by AlphaAgent."""

    return ChatGroq(
        model=LLM_CONFIG.model,
        temperature=temperature,
        max_tokens=max_tokens,
        callbacks=callbacks,
    )


def extract_usage_from_message(message: Any) -> tuple[int, int]:
    """Extract token usage from a LangChain AIMessage when available."""

    usage_metadata = getattr(message, "usage_metadata", None) or {}
    response_metadata = getattr(message, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage", {}) if isinstance(response_metadata, dict) else {}

    input_tokens = (
        usage_metadata.get("input_tokens")
        or token_usage.get("input_tokens")
        or token_usage.get("prompt_tokens")
        or 0
    )
    output_tokens = (
        usage_metadata.get("output_tokens")
        or token_usage.get("output_tokens")
        or token_usage.get("completion_tokens")
        or 0
    )
    return int(input_tokens or 0), int(output_tokens or 0)


def extract_usage_from_llm_result(response: LLMResult) -> tuple[int, int]:
    """Extract usage from an LLMResult across common provider metadata shapes."""

    input_tokens = 0
    output_tokens = 0

    if response.llm_output:
        token_usage = response.llm_output.get("token_usage") or response.llm_output.get("usage") or {}
        input_tokens += int(
            token_usage.get("input_tokens")
            or token_usage.get("prompt_tokens")
            or token_usage.get("cache_read_input_tokens")
            or 0
        )
        output_tokens += int(token_usage.get("output_tokens") or token_usage.get("completion_tokens") or 0)

    for generation_group in response.generations or []:
        for generation in generation_group:
            message = getattr(generation, "message", None)
            if message is not None:
                message_input, message_output = extract_usage_from_message(message)
                input_tokens += message_input
                output_tokens += message_output

    return input_tokens, output_tokens


def invoke_with_tracking(llm: ChatGroq, prompt: str, label: str) -> str:
    """Invoke the LLM and record exact token usage when returned by the provider."""

    response = llm.invoke(prompt)
    input_tokens, output_tokens = extract_usage_from_message(response)
    if input_tokens or output_tokens:
        cost_tracker.add_usage(input_tokens, output_tokens, label=label)
    return str(response.content)
