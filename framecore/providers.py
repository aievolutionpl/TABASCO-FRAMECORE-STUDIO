"""Provider boundary. No invented assets or implicit paid requests."""
from typing import Protocol
from .model import EditorError


class MediaProvider(Protocol):
    id: str
    capabilities: set[str]

    def generate(self, kind: str, request: dict) -> dict:
        """Return local media + provenance, or raise a provider error."""


class ProviderRegistry:
    def __init__(self):
        self.adapters = {}

    def register(self, adapter: MediaProvider):
        self.adapters[adapter.id] = adapter

    def describe(self):
        return [{"id": p.id, "capabilities": sorted(p.capabilities)} for p in self.adapters.values()]

    def generate(self, provider_id, kind, request):
        provider = self.adapters.get(provider_id)
        if not provider or kind not in provider.capabilities:
            raise EditorError(f"Brak skonfigurowanego dostawcy: {kind}. Najpierw dodaj integrację z własnym kluczem.", "provider_unavailable")
        return provider.generate(kind, request)


PROVIDERS = ProviderRegistry()
