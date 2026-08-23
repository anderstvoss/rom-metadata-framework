from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class MetadataProvenance:
    """Origin of one provider-supplied metadata value."""

    source: str
    source_id: str
    authoritative: bool = False
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = self.source.strip().lower()
        source_id = self.source_id.strip()

        if not source:
            raise ValueError("metadata source must not be empty")

        if not source_id:
            raise ValueError("metadata source_id must not be empty")

        normalized_details = {
            str(key).strip(): str(value).strip()
            for key, value in self.details.items()
        }

        if any(not key for key in normalized_details):
            raise ValueError(
                "metadata provenance detail keys must not be empty"
            )

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(
            self,
            "details",
            MappingProxyType(normalized_details),
        )


@dataclass(frozen=True, slots=True)
class MetadataValue(Generic[T]):
    """One metadata value together with its provider provenance."""

    value: T
    provenance: MetadataProvenance


@dataclass(frozen=True, slots=True)
class ReleaseDate:
    """One provider-supplied release date and its applicable region."""

    value: date
    provenance: MetadataProvenance
    region: str | None = None

    def __post_init__(self) -> None:
        if self.region is not None:
            object.__setattr__(
                self,
                "region",
                self.region.strip() or None,
            )


@dataclass(frozen=True, slots=True)
class ExternalIdentifier:
    """One namespaced provider or catalogue identifier."""

    namespace: str
    value: str
    provenance: MetadataProvenance

    def __post_init__(self) -> None:
        namespace = self.namespace.strip().lower()
        value = self.value.strip()

        if not namespace:
            raise ValueError(
                "external identifier namespace must not be empty"
            )

        if not value:
            raise ValueError(
                "external identifier value must not be empty"
            )

        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class PlayerCount:
    """One provider-supplied supported player-count range."""

    minimum: int
    maximum: int
    provenance: MetadataProvenance
    context: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.minimum, bool) or not isinstance(
            self.minimum,
            int,
        ):
            raise TypeError("minimum player count must be an integer")

        if isinstance(self.maximum, bool) or not isinstance(
            self.maximum,
            int,
        ):
            raise TypeError("maximum player count must be an integer")

        if self.minimum < 1:
            raise ValueError("minimum player count must be at least one")

        if self.maximum < self.minimum:
            raise ValueError(
                "maximum player count must not be less than minimum"
            )

        if self.context is not None:
            object.__setattr__(
                self,
                "context",
                self.context.strip() or None,
            )


@dataclass(frozen=True, slots=True)
class AgeRating:
    """One provider-supplied age/content rating."""

    system: str
    rating: str
    provenance: MetadataProvenance
    region: str | None = None

    def __post_init__(self) -> None:
        system = self.system.strip().lower()
        rating = self.rating.strip()

        if not system:
            raise ValueError("age-rating system must not be empty")

        if not rating:
            raise ValueError("age rating must not be empty")

        object.__setattr__(self, "system", system)
        object.__setattr__(self, "rating", rating)

        if self.region is not None:
            object.__setattr__(
                self,
                "region",
                self.region.strip() or None,
            )


@dataclass(frozen=True, slots=True)
class MediaReference:
    """One provider-supplied artwork or media reference."""

    kind: str
    uri: str
    provenance: MetadataProvenance
    width: int | None = None
    height: int | None = None

    def __post_init__(self) -> None:
        kind = self.kind.strip().lower()
        uri = self.uri.strip()

        if not kind:
            raise ValueError("media kind must not be empty")

        if not uri:
            raise ValueError("media URI must not be empty")

        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "uri", uri)

        for name in ("width", "height"):
            value = getattr(self, name)

            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError(
                        f"media {name} must be an integer"
                    )
                if value < 1:
                    raise ValueError(
                        f"media {name} must be greater than zero"
                    )


@dataclass(frozen=True, slots=True)
class ReleaseMetadata:
    """Provider-independent collection of release metadata evidence."""

    titles: tuple[MetadataValue[str], ...] = ()
    descriptions: tuple[MetadataValue[str], ...] = ()
    developers: tuple[MetadataValue[str], ...] = ()
    publishers: tuple[MetadataValue[str], ...] = ()
    genres: tuple[MetadataValue[str], ...] = ()
    release_dates: tuple[ReleaseDate, ...] = ()
    regions: tuple[MetadataValue[str], ...] = ()
    languages: tuple[MetadataValue[str], ...] = ()
    player_counts: tuple[PlayerCount, ...] = ()
    multiplayer_features: tuple[MetadataValue[str], ...] = ()
    age_ratings: tuple[AgeRating, ...] = ()
    media: tuple[MediaReference, ...] = ()
    external_ids: tuple[ExternalIdentifier, ...] = ()
