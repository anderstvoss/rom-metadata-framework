from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class RepresentationIdentity:
    """Physical representation of the source file.

    This describes how content is stored in the source file. It does not
    describe any normalized or reconstructed canonical byte stream.
    """

    kind: str
    format: str
    metadata: Mapping[str, str] = field(
        default_factory=dict,
    )

    def __post_init__(self) -> None:
        kind = self.kind.strip().lower()
        format_name = self.format.strip().lower()

        if not kind:
            raise ValueError(
                "representation kind must not be empty"
            )

        if not format_name:
            raise ValueError(
                "representation format must not be empty"
            )

        metadata = {
            str(key).strip(): str(value).strip()
            for key, value in self.metadata.items()
        }

        if any(not key for key in metadata):
            raise ValueError(
                "representation metadata keys must not be empty"
            )

        object.__setattr__(
            self,
            "kind",
            kind,
        )
        object.__setattr__(
            self,
            "format",
            format_name,
        )
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(metadata),
        )
