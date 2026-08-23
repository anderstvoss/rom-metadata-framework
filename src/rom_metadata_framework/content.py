from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .identity import HashSet


@dataclass(frozen=True, slots=True)
class NormalizedContentIdentity:
    """Identity of normalized content represented by a physical file."""

    kind: str
    hashes: HashSet = field(default_factory=HashSet)
    specialized_identifiers: Mapping[str, str] = field(
        default_factory=dict,
    )
    metadata: Mapping[str, str] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        kind = self.kind.strip().lower()

        if not kind:
            raise ValueError("content identity kind must not be empty")

        object.__setattr__(self, "kind", kind)

        identifiers: dict[str, str] = {}

        for namespace, value in self.specialized_identifiers.items():
            normalized_namespace = str(namespace).strip().lower()
            normalized_value = str(value).strip()

            if not normalized_namespace:
                raise ValueError(
                    "specialized identifier namespace "
                    "must not be empty"
                )

            if not normalized_value:
                raise ValueError(
                    "specialized identifier value "
                    "must not be empty"
                )

            if normalized_namespace in identifiers:
                raise ValueError(
                    "duplicate specialized identifier namespace "
                    f"{normalized_namespace!r}"
                )

            identifiers[
                normalized_namespace
            ] = normalized_value

        object.__setattr__(
            self,
            "specialized_identifiers",
            MappingProxyType(identifiers),
        )

        metadata: dict[str, str] = {}

        for key, value in self.metadata.items():
            normalized_key = str(key).strip()
            normalized_value = str(value).strip()

            if not normalized_key:
                raise ValueError(
                    "content metadata keys must not be empty"
                )

            metadata[normalized_key] = normalized_value

        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(metadata),
        )
