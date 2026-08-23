from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from .canonical import CanonicalReleaseIdentity
from .metadata import ReleaseMetadata


@dataclass(frozen=True, slots=True)
class MetadataProviderResult:
    """Normalized metadata returned from one matched provider record."""

    provider: str
    provider_id: str
    metadata: ReleaseMetadata
    match_method: str | None = None
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        provider = self.provider.strip().lower()
        provider_id = self.provider_id.strip()

        if not provider:
            raise ValueError("metadata provider must not be empty")

        if not provider_id:
            raise ValueError("metadata provider_id must not be empty")

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "provider_id", provider_id)

        if self.match_method is not None:
            object.__setattr__(
                self,
                "match_method",
                self.match_method.strip().lower() or None,
            )

        normalized_details = {
            str(key).strip(): str(value).strip()
            for key, value in self.details.items()
        }

        if any(not key for key in normalized_details):
            raise ValueError(
                "metadata provider detail keys must not be empty"
            )

        object.__setattr__(
            self,
            "details",
            MappingProxyType(normalized_details),
        )


@runtime_checkable
class MetadataProvider(Protocol):
    """Provider that enriches one resolved release identity."""

    @property
    def name(self) -> str:
        """Stable provider name."""
        ...

    def lookup_metadata(
        self,
        identity: CanonicalReleaseIdentity,
    ) -> MetadataProviderResult | None:
        """Return metadata for one release, or None when unmatched."""
        ...
