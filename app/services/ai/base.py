"""AIProvider interface and the shared message/result shapes.

Providers are interchangeable and selected at runtime by
``app.services.ai.registry``. Nothing above this layer knows whether an answer
came from a local model or a deterministic fallback.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class Completion:
    """A model answer plus the provenance the UI needs to be honest about it."""

    text: str
    provider: str
    model: str = ""
    # True when no language model was involved and the text is a fixed template.
    is_fallback: bool = False
    latency_ms: int = 0
    # Populated when the provider refused or could not answer.
    error: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text.strip())


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    provider: str
    model: str = ""
    is_fallback: bool = False
    dim: int = 0


class AIProvider(abc.ABC):
    """Capability-advertising text provider.

    Implementations must be safe to call from a threadpool and must never
    raise: failures are returned as a ``Completion`` carrying ``error``, so a
    provider outage degrades the feature instead of breaking the request.
    """

    name: str = "base"
    #: Whether this provider needs a network call.
    requires_network: bool = True
    #: Whether this provider can produce free-form generative text.
    generative: bool = True

    @abc.abstractmethod
    def health(self) -> tuple[bool, str]:
        """Return ``(healthy, detail)``. Must be cheap and must not raise."""

    @abc.abstractmethod
    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
        timeout: int | None = None,
    ) -> Completion:
        """Produce an answer for a chat-style message list."""

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Embed texts. Providers without embeddings should not override this."""
        raise NotImplementedError(f"{self.name} does not provide embeddings")

    @property
    def supports_embeddings(self) -> bool:
        return type(self).embed is not AIProvider.embed
