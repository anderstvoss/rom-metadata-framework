from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from .platforms import canonical_platform_name


class IntegrityStatus(StrEnum):
    """Normalized outcome of specialist artifact-integrity verification.

    VERIFIED means the verifier positively established the integrity
    property it evaluates.

    FAILED means the verifier positively established that the artifact
    violates that integrity property.

    INCONCLUSIVE means verification ran but available evidence could not
    establish either validity or failure. It must not be interpreted as
    corruption.
    """

    VERIFIED = "verified"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class IntegrityEvidence:
    """One specialist observation about artifact or media integrity."""

    source: str
    method: str
    result: str
    details: Mapping[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        source = self.source.strip().lower()
        method = self.method.strip().lower()
        result = self.result.strip()

        if not source:
            raise ValueError(
                "integrity evidence source must not be empty"
            )

        if not method:
            raise ValueError(
                "integrity evidence method must not be empty"
            )

        if not result:
            raise ValueError(
                "integrity evidence result must not be empty"
            )

        details = {
            str(key).strip(): str(value).strip()
            for key, value in self.details.items()
        }

        if any(not key for key in details):
            raise ValueError(
                "integrity evidence detail keys must not be empty"
            )

        object.__setattr__(
            self,
            "source",
            source,
        )
        object.__setattr__(
            self,
            "method",
            method,
        )
        object.__setattr__(
            self,
            "result",
            result,
        )
        object.__setattr__(
            self,
            "details",
            MappingProxyType(details),
        )


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    """Specialist integrity assessment of one physical artifact."""

    platform: str
    verifier: str
    status: IntegrityStatus
    evidence: tuple[IntegrityEvidence, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        platform = canonical_platform_name(
            self.platform
        )
        verifier = self.verifier.strip()

        if not verifier:
            raise ValueError(
                "integrity verifier name must not be empty"
            )

        reasons = tuple(
            reason.strip()
            for reason in self.reasons
            if reason.strip()
        )

        object.__setattr__(
            self,
            "platform",
            platform,
        )
        object.__setattr__(
            self,
            "verifier",
            verifier,
        )
        object.__setattr__(
            self,
            "reasons",
            reasons,
        )

    @property
    def verified(self) -> bool:
        """Return whether specialist integrity was positively verified."""

        return self.status is IntegrityStatus.VERIFIED


class IntegrityProbeStatus(StrEnum):
    """Outcome of probing one specialist integrity verifier."""

    UNSUPPORTED = "unsupported"
    SUPPORTED = "supported"
    BACKEND_UNAVAILABLE = "backend-unavailable"
    BACKEND_FAILURE = "backend-failure"


@dataclass(frozen=True, slots=True)
class IntegrityProbe:
    """Structured applicability result from one integrity verifier."""

    verifier: str
    status: IntegrityProbeStatus
    reason: str | None = None
    details: Mapping[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        verifier = self.verifier.strip()

        if not verifier:
            raise ValueError(
                "integrity verifier name must not be empty"
            )

        reason = (
            self.reason.strip()
            if self.reason is not None
            else None
        )

        details = {
            str(key).strip(): str(value).strip()
            for key, value in self.details.items()
        }

        if any(not key for key in details):
            raise ValueError(
                "integrity probe detail keys must not be empty"
            )

        object.__setattr__(
            self,
            "verifier",
            verifier,
        )
        object.__setattr__(
            self,
            "reason",
            reason or None,
        )
        object.__setattr__(
            self,
            "details",
            MappingProxyType(details),
        )

    @property
    def supported(self) -> bool:
        return (
            self.status
            is IntegrityProbeStatus.SUPPORTED
        )

    @property
    def terminal_failure(self) -> bool:
        return self.status in {
            IntegrityProbeStatus.BACKEND_UNAVAILABLE,
            IntegrityProbeStatus.BACKEND_FAILURE,
        }


@runtime_checkable
class IntegrityVerifier(Protocol):
    """Specialist verifier for physical artifact/media integrity."""

    @property
    def name(self) -> str:
        """Stable verifier name."""
        ...

    def probe(
        self,
        path: Path,
    ) -> IntegrityProbe:
        """Classify whether this verifier can handle the artifact."""
        ...

    def verify(
        self,
        path: Path,
    ) -> IntegrityReport:
        """Perform specialist integrity validation."""
        ...
