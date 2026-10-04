"""Ollama-backed provider.

Talks to a local Ollama daemon over HTTP, so no API key leaves the machine and
the whole stack works without internet. The model is configurable via
``OLLAMA_MODEL`` (default ``qwen2.5:7b``, which handles English and Hindi
reasonably and Tamil less well - the UI always lets the user switch language
or ask for a simpler explanation).
"""
from __future__ import annotations

import logging
import time

import httpx

from app.config import settings
from app.services.ai.base import AIProvider, Completion, EmbeddingResult, Message

log = logging.getLogger("nirvaan.ai.ollama")


class OllamaProvider(AIProvider):
    name = "ollama"
    requires_network = False  # localhost only
    generative = True

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        embed_model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.embed_model = embed_model or settings.ollama_embed_model
        self.timeout = timeout or settings.ollama_timeout_seconds

    # -- health ------------------------------------------------------------

    def health(self) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            names = [m.get("name", "") for m in response.json().get("models", [])]
        except Exception as exc:  # noqa: BLE001 - health must never raise
            return False, f"Ollama unreachable at {self.base_url}: {exc}"

        if not names:
            return False, "Ollama is running but has no models pulled."
        if self.model not in names:
            return (
                False,
                f"Model {self.model} is not pulled. Available: {', '.join(names[:5])}. "
                f"Run: ollama pull {self.model}",
            )
        return True, f"Ollama ready with {self.model}"

    # -- completion --------------------------------------------------------

    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
        timeout: int | None = None,
    ) -> Completion:
        payload = {
            "model": self.model,
            "messages": [m.as_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                # Low repeat penalty keeps the careful, repetitive safety
                # phrasing we deliberately want in explanations.
                "repeat_penalty": 1.05,
            },
        }

        started = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout or self.timeout) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            return Completion(
                text="",
                provider=self.name,
                model=self.model,
                error="The local model took too long to respond.",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("ollama completion failed: %s", exc)
            return Completion(
                text="",
                provider=self.name,
                model=self.model,
                error=f"Local model unavailable: {exc}",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        text = (data.get("message") or {}).get("content", "") or ""
        return Completion(
            text=text.strip(),
            provider=self.name,
            model=self.model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            usage={
                "prompt_eval_count": data.get("prompt_eval_count", 0),
                "eval_count": data.get("eval_count", 0),
            },
        )

    # -- embeddings --------------------------------------------------------

    def embed(self, texts: list[str]) -> EmbeddingResult:
        vectors: list[list[float]] = []
        try:
            with httpx.Client(timeout=self.timeout) as client:
                for text in texts:
                    response = client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.embed_model, "prompt": text},
                    )
                    response.raise_for_status()
                    vectors.append(response.json().get("embedding") or [])
        except Exception as exc:  # noqa: BLE001
            log.warning("ollama embeddings failed: %s", exc)
            raise RuntimeError(f"Ollama embeddings unavailable: {exc}") from exc

        dim = len(vectors[0]) if vectors and vectors[0] else 0
        return EmbeddingResult(
            vectors=vectors, provider=self.name, model=self.embed_model, dim=dim
        )
