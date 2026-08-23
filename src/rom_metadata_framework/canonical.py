from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .provenance import CatalogueEvidence


CONTENT_MATCH_METHODS = frozenset({
    "SHA256",
    "SHA1",
    "MD5",
    "CRC",
})


@dataclass(frozen=True, slots=True)
class IdentificationEvidence:
    """One independent piece of evidence supporting an identity."""

    source: str
    method: str
    authoritative: bool = False
    value: str | None = None
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = self.source.strip().lower()
        method = self.method.strip()

        if not source:
            raise ValueError("evidence source must not be empty")

        if not method:
            raise ValueError("evidence method must not be empty")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "method", method)

        if self.value is not None:
            object.__setattr__(
                self,
                "value",
                self.value.strip() or None,
            )

        normalized_details = {
            str(key).strip(): str(value).strip()
            for key, value in self.details.items()
        }

        if any(not key for key in normalized_details):
            raise ValueError("evidence detail keys must not be empty")

        object.__setattr__(
            self,
            "details",
            MappingProxyType(normalized_details),
        )


@dataclass(frozen=True, slots=True)
class CanonicalReleaseIdentity:
    """Provider-independent normalized identity for one game release."""

    release_name: str
    platform: str

    source: str
    source_id: str

    title: str | None = None

    external_ids: Mapping[str, str] = field(default_factory=dict)
    evidence: tuple[IdentificationEvidence, ...] = ()
    catalogue_evidence: tuple[CatalogueEvidence, ...] = ()
    conflicts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "release_name",
            "platform",
            "source",
            "source_id",
        ):
            value = getattr(self, name).strip()

            if not value:
                raise ValueError(f"{name} must not be empty")

            if name == "source":
                value = value.lower()

            object.__setattr__(self, name, value)

        if self.title is not None:
            object.__setattr__(
                self,
                "title",
                self.title.strip() or None,
            )

        normalized_ids = {
            str(key).strip().lower(): str(value).strip()
            for key, value in self.external_ids.items()
            if str(value).strip()
        }

        if any(not key for key in normalized_ids):
            raise ValueError("external ID namespaces must not be empty")

        object.__setattr__(
            self,
            "external_ids",
            MappingProxyType(normalized_ids),
        )

        normalized_conflicts = tuple(
            conflict.strip()
            for conflict in self.conflicts
            if conflict.strip()
        )

        object.__setattr__(
            self,
            "conflicts",
            normalized_conflicts,
        )

    @property
    def has_authoritative_content_match(self) -> bool:
        return any(
            evidence.authoritative
            and evidence.method in CONTENT_MATCH_METHODS
            for evidence in self.evidence
        )

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)
