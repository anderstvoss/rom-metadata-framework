from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from .platforms import canonical_platform_name
from .selection import component_supports_platform


@dataclass(frozen=True, slots=True)
class PlatformEvidence:
    """One observation supporting a platform candidate."""

    source: str
    method: str
    value: str
    strength: int
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = self.source.strip().lower()
        method = self.method.strip().lower()
        value = self.value.strip()

        if not source:
            raise ValueError("platform evidence source must not be empty")

        if not method:
            raise ValueError("platform evidence method must not be empty")

        if not value:
            raise ValueError("platform evidence value must not be empty")

        if isinstance(self.strength, bool) or not isinstance(
            self.strength,
            int,
        ):
            raise TypeError("platform evidence strength must be an integer")

        if not 0 <= self.strength <= 100:
            raise ValueError("platform evidence strength must be between 0 and 100")

        normalized_details = {
            str(key).strip(): str(value).strip() for key, value in self.details.items()
        }

        if any(not key for key in normalized_details):
            raise ValueError("platform evidence detail keys must not be empty")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "value", value)
        object.__setattr__(
            self,
            "details",
            MappingProxyType(normalized_details),
        )


@dataclass(frozen=True, slots=True)
class PlatformCandidate:
    """One possible normalized platform inferred from file evidence."""

    platform: str
    confidence: int
    evidence: tuple[PlatformEvidence, ...] = ()

    def __post_init__(self) -> None:
        platform = canonical_platform_name(self.platform)

        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence,
            int,
        ):
            raise TypeError("platform confidence must be an integer")

        if not 0 <= self.confidence <= 100:
            raise ValueError("platform confidence must be between 0 and 100")

        object.__setattr__(self, "platform", platform)


@dataclass(frozen=True, slots=True)
class PlatformDetection:
    """Platform inference result before game/release identification."""

    candidates: tuple[PlatformCandidate, ...] = ()

    @property
    def best(self) -> PlatformCandidate | None:
        if not self.candidates:
            return None

        return max(
            self.candidates,
            key=lambda candidate: candidate.confidence,
        )

    @property
    def is_ambiguous(self) -> bool:
        if len(self.candidates) < 2:
            return False

        ranked = sorted(
            self.candidates,
            key=lambda candidate: candidate.confidence,
            reverse=True,
        )

        return ranked[0].confidence == ranked[1].confidence


@runtime_checkable
class PlatformDetector(Protocol):
    """Interface for content/container-based platform detectors."""

    @property
    def name(self) -> str:
        """Stable detector name."""
        ...

    def detect(self, path: Path) -> PlatformDetection:
        """Inspect a file and return zero or more platform candidates."""
        ...


@dataclass(frozen=True, slots=True)
class CompositePlatformDetector:
    """Combine platform evidence from independent detectors."""

    detectors: tuple[PlatformDetector, ...]
    preferred_platform: str | None = None
    restrict_platform: bool = False

    def __post_init__(self) -> None:
        if self.preferred_platform is not None:
            object.__setattr__(
                self,
                "preferred_platform",
                canonical_platform_name(
                    self.preferred_platform
                ),
            )

        if (
            self.restrict_platform
            and self.preferred_platform is None
        ):
            raise ValueError(
                "restricted detector requires a preferred platform"
            )

    @property
    def name(self) -> str:
        return "composite"

    def detect(
        self,
        path: Path,
        *,
        preferred_platform: str | None = None,
        restrict_platform: bool = False,
    ) -> PlatformDetection:
        """Run detectors with optional platform-directed routing.

        A preferred platform is tested first. If it positively identifies
        the requested platform, unrelated detectors are not invoked.

        If the preferred platform does not match and routing is unrestricted,
        the remaining detectors run as normal fallback.

        Restricted routing invokes only components that own the requested
        platform.
        """

        path = Path(path)
        candidates: dict[str, PlatformCandidate] = {}

        preferred_platform = (
            preferred_platform
            if preferred_platform is not None
            else self.preferred_platform
        )
        restrict_platform = (
            restrict_platform
            or self.restrict_platform
        )

        preferred = ()
        remaining = self.detectors

        if preferred_platform is not None:
            preferred_platform = canonical_platform_name(
                preferred_platform
            )

            preferred = tuple(
                detector
                for detector in self.detectors
                if component_supports_platform(
                    detector.name,
                    preferred_platform,
                )
            )
            remaining = tuple(
                detector
                for detector in self.detectors
                if detector not in preferred
            )

        def run_detectors(detectors):
            for detector in detectors:
                detection = detector.detect(path)

                for candidate in detection.candidates:
                    existing = candidates.get(
                        candidate.platform
                    )

                    if existing is None:
                        candidates[
                            candidate.platform
                        ] = candidate
                        continue

                    candidates[
                        candidate.platform
                    ] = PlatformCandidate(
                        platform=candidate.platform,
                        confidence=max(
                            existing.confidence,
                            candidate.confidence,
                        ),
                        evidence=(
                            *existing.evidence,
                            *candidate.evidence,
                        ),
                    )

        if preferred:
            run_detectors(preferred)

            if (
                preferred_platform is not None
                and preferred_platform in candidates
            ):
                return PlatformDetection(
                    candidates=tuple(
                        candidates.values()
                    ),
                )

            if restrict_platform:
                return PlatformDetection(
                    candidates=tuple(
                        candidates.values()
                    ),
                )

        elif restrict_platform:
            return PlatformDetection()

        run_detectors(remaining)

        return PlatformDetection(
            candidates=tuple(candidates.values()),
        )
