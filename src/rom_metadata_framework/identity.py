from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class HashSet:
    """Normalized cryptographic and checksum identifiers."""

    crc32: str | None = None
    md5: str | None = None
    sha1: str | None = None
    sha256: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("crc32", self.crc32),
            ("md5", self.md5),
            ("sha1", self.sha1),
            ("sha256", self.sha256),
        ):
            if value is None:
                continue

            normalized = value.strip().lower()

            expected_lengths = {
                "crc32": 8,
                "md5": 32,
                "sha1": 40,
                "sha256": 64,
            }

            if len(normalized) != expected_lengths[name]:
                raise ValueError(
                    f"{name} must contain exactly "
                    f"{expected_lengths[name]} hexadecimal characters"
                )

            if any(ch not in "0123456789abcdef" for ch in normalized):
                raise ValueError(f"{name} must contain only hexadecimal characters")

            object.__setattr__(self, name, normalized)


@dataclass(frozen=True, slots=True)
class AdapterProvenance:
    """Identifies the adapter implementation that produced an identity."""

    name: str
    version: str | None = None
    backend: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("adapter name must not be empty")

        object.__setattr__(self, "name", self.name.strip())

        if self.version is not None:
            object.__setattr__(self, "version", self.version.strip() or None)

        if self.backend is not None:
            object.__setattr__(self, "backend", self.backend.strip() or None)


@dataclass(frozen=True, slots=True)
class RomIdentity:
    """Format-neutral identity information for one ROM or disc image."""

    platform: str | None = None
    format: str | None = None

    file_name: str | None = None
    file_size: int | None = None

    hashes: HashSet = field(default_factory=HashSet)

    serial: str | None = None
    product_code: str | None = None
    title_id: str | None = None

    specialized_identifiers: Mapping[str, str] = field(default_factory=dict)
    media_metadata: Mapping[str, str] = field(default_factory=dict)

    adapter: AdapterProvenance | None = None

    def __post_init__(self) -> None:
        for name in (
            "platform",
            "format",
            "file_name",
            "serial",
            "product_code",
            "title_id",
        ):
            value = getattr(self, name)

            if value is not None:
                object.__setattr__(self, name, value.strip() or None)

        if self.platform is not None:
            from .platforms import (
                UnknownPlatformError,
                canonical_platform_name,
            )

            try:
                canonical_platform = canonical_platform_name(
                    self.platform
                )
            except UnknownPlatformError:
                canonical_platform = self.platform

            object.__setattr__(
                self,
                "platform",
                canonical_platform,
            )

        if self.file_size is not None:
            if isinstance(self.file_size, bool) or not isinstance(
                self.file_size,
                int,
            ):
                raise TypeError("file_size must be an integer or None")

            if self.file_size < 0:
                raise ValueError("file_size must not be negative")

        normalized_identifiers: dict[str, str] = {}

        for namespace, value in self.specialized_identifiers.items():
            normalized_namespace = str(namespace).strip().lower()
            normalized_value = str(value).strip()

            if not normalized_namespace:
                raise ValueError(
                    "specialized identifier namespaces must not be empty"
                )

            if not normalized_value:
                raise ValueError(
                    "specialized identifier values must not be empty"
                )

            if normalized_namespace in normalized_identifiers:
                raise ValueError(
                    "duplicate specialized identifier namespace "
                    f"{normalized_namespace!r}"
                )

            normalized_identifiers[normalized_namespace] = normalized_value

        object.__setattr__(
            self,
            "specialized_identifiers",
            MappingProxyType(normalized_identifiers),
        )

        normalized_metadata: dict[str, str] = {}

        for key, value in self.media_metadata.items():
            normalized_key = str(key).strip()
            normalized_value = str(value).strip()

            if not normalized_key:
                raise ValueError("media metadata keys must not be empty")

            normalized_metadata[normalized_key] = normalized_value

        object.__setattr__(
            self,
            "media_metadata",
            MappingProxyType(normalized_metadata),
        )
