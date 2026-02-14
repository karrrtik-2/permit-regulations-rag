"""
LLM client wrapper for HeavyHaul AI.

Provides a unified interface for interacting with Groq LLM
for streaming and non-streaming completions.
"""

import logging
from typing import Any, Dict, Iterator, List, Optional

from groq import Groq

from config.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper around Groq LLM for centralized model interaction.

    Provides streaming and non-streaming chat completion methods
    with configurable model parameters.
    """

    def __init__(self) -> None:
        """Initialize the LLM client with configured API key."""
        self._client = Groq(api_key=settings.llm.groq_api_key)

    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[Any]:
        """Create a streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model name override. Defaults to config.
            temperature: Temperature override. Defaults to config.
            max_tokens: Max tokens override. Defaults to config.

        Returns:
            Iterator of streaming response chunks.
        """
        return self._client.chat.completions.create(
            model=model or settings.llm.groq_model,
            messages=messages,
            temperature=temperature or settings.llm.default_temperature,
            top_p=settings.llm.default_top_p,
            max_tokens=max_tokens or settings.llm.default_max_tokens,
            stream=True,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Create a non-streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model name override.
            temperature: Temperature override.
            max_tokens: Max tokens override.

        Returns:
            The complete response text.
        """
        response = ""
        for chunk in self.stream_chat(messages, model, temperature, max_tokens):
            content = chunk.choices[0].delta.content
            if content is not None:
                response += content
        return response


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    """Get the singleton LLM client instance.

    Returns:
        Configured LLMClient.
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
