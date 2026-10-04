"""Modular AI provider layer.

Nothing outside this package constructs a provider directly - callers use
``registry`` so provider choice, health checks and failover stay in one place.
"""
from app.services.ai.base import (
    AIProvider,
    Completion,
    EmbeddingResult,
    Message,
)
from app.services.ai.local_provider import LocalAIProvider
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.registry import ProviderRegistry, registry

__all__ = [
    "AIProvider",
    "Completion",
    "EmbeddingResult",
    "Message",
    "LocalAIProvider",
    "OllamaProvider",
    "ProviderRegistry",
    "registry",
]
