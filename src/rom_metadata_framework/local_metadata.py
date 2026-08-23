from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Generic, TypeVar

from .platforms import canonical_platform_name

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LocalMetadataProvenance:
    """Origin of one value extracted from the represented artifact."""

    source: str
    method: str
    raw_value: str | None = None
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = self.source.strip().lower()
        method = self.method.strip().lower()

        if not source:
            raise ValueError("local metadata source must not be empty")

        if not method:
            raise ValueError("local metadata method must not be empty")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "method", method)

        if self.raw_value is not None:
            object.__setattr__(
                self,
                "raw_value",
                str(self.raw_value).strip() or None,
            )

        normalized_details = {
            str(key).strip(): str(value).strip() for key, value in self.details.items()
        }

        if any(not key for key in normalized_details):
            raise ValueError("local metadata detail keys must not be empty")

        object.__setattr__(
            self,
            "details",
            MappingProxyType(normalized_details),
        )


@dataclass(frozen=True, slots=True)
class LocalMetadataValue(Generic[T]):
    """One locally extracted value with provenance."""

    value: T
    provenance: LocalMetadataProvenance


@dataclass(frozen=True, slots=True)
class LocalIdentifier:
    """One platform-native or content-native identifier."""

    namespace: str
    value: str
    provenance: LocalMetadataProvenance

    def __post_init__(self) -> None:
        namespace = self.namespace.strip().lower()
        value = self.value.strip()

        if not namespace:
            raise ValueError("local identifier namespace must not be empty")

        if not value:
            raise ValueError("local identifier value must not be empty")

        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class LocalTimestamp:
    """One timestamp encoded by the represented artifact."""

    kind: str
    value: datetime
    provenance: LocalMetadataProvenance

    def __post_init__(self) -> None:
        kind = self.kind.strip().lower()

        if not kind:
            raise ValueError("local timestamp kind must not be empty")

        object.__setattr__(self, "kind", kind)


@dataclass(frozen=True, slots=True)
class LocalPlayerCount:
    """Locally encoded player-count information."""

    minimum: int
    maximum: int
    provenance: LocalMetadataProvenance
    context: str | None = None

    def __post_init__(self) -> None:
        for name in ("minimum", "maximum"):
            value = getattr(self, name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} player count must be an integer")

        if self.minimum < 1:
            raise ValueError("minimum player count must be at least one")

        if self.maximum < self.minimum:
            raise ValueError("maximum player count must not be less than minimum")

        if self.context is not None:
            object.__setattr__(
                self,
                "context",
                self.context.strip() or None,
            )


@dataclass(frozen=True, slots=True)
class LocalContentMetadata:
    """System-independent metadata extracted from the artifact itself.

    Every field is optional evidence. Platform adapters populate only
    values that their represented formats expose reliably. Unknown or
    unavailable values remain absent rather than being inferred.
    """

    platform: str | None = None

    titles: tuple[LocalMetadataValue[str], ...] = ()
    short_titles: tuple[LocalMetadataValue[str], ...] = ()

    identifiers: tuple[LocalIdentifier, ...] = ()

    release_revisions: tuple[LocalMetadataValue[str], ...] = ()
    software_versions: tuple[LocalMetadataValue[str], ...] = ()
    executable_versions: tuple[LocalMetadataValue[str], ...] = ()

    disc_numbers: tuple[LocalMetadataValue[int], ...] = ()
    disc_totals: tuple[LocalMetadataValue[int], ...] = ()

    regions: tuple[LocalMetadataValue[str], ...] = ()
    countries: tuple[LocalMetadataValue[str], ...] = ()
    languages: tuple[LocalMetadataValue[str], ...] = ()

    developers: tuple[LocalMetadataValue[str], ...] = ()
    publishers: tuple[LocalMetadataValue[str], ...] = ()
    manufacturers: tuple[LocalMetadataValue[str], ...] = ()
    maker_codes: tuple[LocalMetadataValue[str], ...] = ()

    timestamps: tuple[LocalTimestamp, ...] = ()

    ratings: tuple[LocalMetadataValue[str], ...] = ()
    player_counts: tuple[LocalPlayerCount, ...] = ()
    multiplayer_features: tuple[LocalMetadataValue[str], ...] = ()

    hardware: Mapping[str, str] = field(default_factory=dict)
    media: Mapping[str, str] = field(default_factory=dict)
    boot: Mapping[str, str] = field(default_factory=dict)
    native_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.platform is not None:
            object.__setattr__(
                self,
                "platform",
                canonical_platform_name(self.platform),
            )

        for name in (
            "hardware",
            "media",
            "boot",
            "native_metadata",
        ):
            mapping = {
                str(key).strip(): str(value).strip()
                for key, value in getattr(self, name).items()
            }

            if any(not key for key in mapping):
                raise ValueError(f"{name} metadata keys must not be empty")

            object.__setattr__(
                self,
                name,
                MappingProxyType(mapping),
            )

    @property
    def empty(self) -> bool:
        """Return whether no locally extracted metadata is present."""

        return (
            self.platform is None
            and not self.titles
            and not self.short_titles
            and not self.identifiers
            and not self.release_revisions
            and not self.software_versions
            and not self.executable_versions
            and not self.disc_numbers
            and not self.disc_totals
            and not self.regions
            and not self.countries
            and not self.languages
            and not self.developers
            and not self.publishers
            and not self.manufacturers
            and not self.maker_codes
            and not self.timestamps
            and not self.ratings
            and not self.player_counts
            and not self.multiplayer_features
            and not self.hardware
            and not self.media
            and not self.boot
            and not self.native_metadata
        )
