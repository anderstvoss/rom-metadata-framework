from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from .identity import RomIdentity


class ResolverUnavailableError(RuntimeError):
    """Raised when a resolver cannot currently be reached or used."""



@dataclass(frozen=True, slots=True)
class ResolvedMetadata:
    """Human-readable metadata returned by a resolver."""

    title: str
    provider: str

    platform: str | None = None
    region: str | None = None
    release_date: str | None = None

    external_ids: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        title = self.title.strip()
        provider = self.provider.strip()

        if not title:
            raise ValueError("resolved title must not be empty")

        if not provider:
            raise ValueError("metadata provider must not be empty")

        object.__setattr__(self, "title", title)
        object.__setattr__(self, "provider", provider)

        for name in ("platform", "region", "release_date"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, value.strip() or None)

        normalized_ids = {
            str(key).strip(): str(value).strip()
            for key, value in self.external_ids.items()
        }

        if any(not key for key in normalized_ids):
            raise ValueError("external ID keys must not be empty")

        object.__setattr__(
            self,
            "external_ids",
            MappingProxyType(normalized_ids),
        )


@runtime_checkable
class MetadataResolver(Protocol):
    """Interface implemented by metadata providers."""

    @property
    def name(self) -> str:
        """Stable resolver/provider name."""
        ...

    def resolve(self, identity: RomIdentity) -> ResolvedMetadata | None:
        """Resolve normalized identity into human-readable metadata."""
        ...
