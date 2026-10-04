"""Provider selection and failover.

``AI_PROVIDER_ORDER`` lists providers by preference. The first healthy one
handles the request; if it fails mid-call the next is tried, and
``LocalAIProvider`` is always appended as the last resort so a request can
never end with nothing to say.

Health results are cached briefly so a dead daemon is not probed on every
keystroke. The cache is ``app.services.cache``: shared by every worker when
Redis is configured, per process otherwise.
"""
from __future__ import annotations

import logging
import threading

from app.config import settings
from app.services import cache
from app.services.ai.base import AIProvider, Completion, EmbeddingResult, Message
from app.services.ai.local_provider import LocalAIProvider
from app.services.ai.ollama_provider import OllamaProvider

log = logging.getLogger("nirvaan.ai.registry")

HEALTH_TTL_SECONDS = 30

_BUILDERS: dict[str, type[AIProvider]] = {
    "ollama": OllamaProvider,
    "local": LocalAIProvider,
}


class ProviderRegistry:
    def __init__(self, order: list[str] | None = None) -> None:
        self._order = order or settings.provider_order
        self._instances: dict[str, AIProvider] = {}
        self._lock = threading.Lock()

    # -- instances ---------------------------------------------------------

    def get(self, name: str) -> AIProvider | None:
        with self._lock:
            if name in self._instances:
                return self._instances[name]
            builder = _BUILDERS.get(name)
            if builder is None:
                log.warning("unknown AI provider configured: %s", name)
                return None
            instance = builder()
            self._instances[name] = instance
            return instance

    @property
    def order(self) -> list[str]:
        """Configured order, with ``local`` guaranteed last."""
        names = [n for n in self._order if n in _BUILDERS]
        if "local" not in names:
            names.append("local")
        return names

    # -- health ------------------------------------------------------------

    @staticmethod
    def _health_key(name: str) -> str:
        return f"ai:health:{name}"

    def _remember_health(self, name: str, healthy: bool, detail: str) -> None:
        cache.set(self._health_key(name), [bool(healthy), str(detail)], ttl=HEALTH_TTL_SECONDS)

    def health(self, name: str, *, force: bool = False) -> tuple[bool, str]:
        if not force:
            cached = cache.get(self._health_key(name))
            if isinstance(cached, list) and len(cached) == 2:
                return bool(cached[0]), str(cached[1])

        provider = self.get(name)
        if provider is None:
            result = (False, f"Provider {name} is not registered")
        else:
            try:
                result = provider.health()
            except Exception as exc:  # noqa: BLE001 - health must not raise
                result = (False, f"{name} health check raised: {exc}")

        self._remember_health(name, result[0], result[1])
        return result

    def health_report(self) -> list[dict[str, object]]:
        """Used by /api/health and the admin console."""
        report = []
        for name in self.order:
            healthy, detail = self.health(name)
            provider = self.get(name)
            report.append(
                {
                    "name": name,
                    "healthy": healthy,
                    "detail": detail,
                    "generative": bool(provider and provider.generative),
                    "requires_network": bool(provider and provider.requires_network),
                    "supports_embeddings": bool(provider and provider.supports_embeddings),
                }
            )
        return report

    def active(self) -> AIProvider:
        """First healthy provider, else the deterministic local one."""
        for name in self.order:
            healthy, _ = self.health(name)
            if healthy:
                provider = self.get(name)
                if provider is not None:
                    return provider
        return self.get("local") or LocalAIProvider()

    # -- calls -------------------------------------------------------------

    def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
        prefer: str | None = None,
    ) -> Completion:
        """Try providers in order until one returns usable text."""
        names = self.order
        if prefer and prefer in _BUILDERS:
            names = [prefer] + [n for n in names if n != prefer]

        last: Completion | None = None
        for name in names:
            healthy, detail = self.health(name)
            if not healthy:
                last = Completion(text="", provider=name, error=detail)
                continue

            provider = self.get(name)
            if provider is None:
                continue

            try:
                result = provider.complete(
                    messages, temperature=temperature, max_tokens=max_tokens
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("provider %s raised: %s", name, exc)
                result = Completion(text="", provider=name, error=str(exc))

            if result.ok:
                return result

            # Mark unhealthy so the next request skips it quickly.
            self._remember_health(name, False, result.error or "no output")
            last = result

        local = self.get("local") or LocalAIProvider()
        fallback = local.complete(messages, temperature=temperature, max_tokens=max_tokens)
        if last and last.error:
            fallback.usage["upstream_error"] = last.error
        return fallback

    def embed(self, texts: list[str], *, prefer: str | None = None) -> EmbeddingResult:
        names = [prefer] if prefer else list(self.order)
        for name in names:
            provider = self.get(name)
            if provider is None or not provider.supports_embeddings:
                continue
            healthy, _ = self.health(name)
            if not healthy:
                continue
            try:
                return provider.embed(texts)
            except Exception as exc:  # noqa: BLE001
                log.warning("embeddings via %s failed: %s", name, exc)
                continue

        return (self.get("local") or LocalAIProvider()).embed(texts)


# Module-level singleton used throughout the app.
registry = ProviderRegistry()
