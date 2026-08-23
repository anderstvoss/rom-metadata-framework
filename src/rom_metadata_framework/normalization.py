from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from .content import NormalizedContentIdentity
from .local_metadata import LocalContentMetadata
from .representation import RepresentationIdentity


@runtime_checkable
class NormalizationResult(Protocol):
    """Complete evidence returned by a normalization adapter."""

    content: NormalizedContentIdentity
    local_metadata: LocalContentMetadata | None
    physical_representation: RepresentationIdentity | None


class NormalizerProbeStatus(str, Enum):
    """Outcome of determining whether a normalizer can handle a source."""

    UNSUPPORTED = "unsupported"
    SUPPORTED = "supported"
    UNSAFE = "unsafe"
    BACKEND_UNAVAILABLE = "backend-unavailable"
    BACKEND_FAILURE = "backend-failure"


@dataclass(frozen=True, slots=True)
class NormalizerProbe:
    """Structured result of probing one normalization adapter."""

    normalizer: str
    status: NormalizerProbeStatus
    reason: str | None = None
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = self.normalizer.strip()

        if not name:
            raise ValueError(
                "normalizer name must not be empty"
            )

        object.__setattr__(
            self,
            "normalizer",
            name,
        )

        reason = (
            self.reason.strip()
            if self.reason is not None
            else None
        )

        object.__setattr__(
            self,
            "reason",
            reason or None,
        )

        details = (
            {}
            if self.details is None
            else {
                str(key).strip(): str(value).strip()
                for key, value in self.details.items()
            }
        )

        if any(not key for key in details):
            raise ValueError(
                "probe detail keys must not be empty"
            )

        object.__setattr__(
            self,
            "details",
            MappingProxyType(details),
        )

    @property
    def supported(self) -> bool:
        """Return whether normalization can safely proceed."""

        return self.status is NormalizerProbeStatus.SUPPORTED

    @property
    def terminal_failure(self) -> bool:
        """Return whether the probe observed a meaningful failure."""

        return self.status in {
            NormalizerProbeStatus.UNSAFE,
            NormalizerProbeStatus.BACKEND_UNAVAILABLE,
            NormalizerProbeStatus.BACKEND_FAILURE,
        }
