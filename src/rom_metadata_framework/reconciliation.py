from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .detection import PlatformDetection


class PlatformReconciliationStatus(StrEnum):
    """Relationship between local and provider platform evidence."""

    AGREEMENT = "agreement"
    PROVIDER_ONLY = "provider_only"
    LOCAL_ONLY = "local_only"
    AMBIGUOUS = "ambiguous"
    CONFLICT = "conflict"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class PlatformReconciliation:
    """Normalized result of comparing local and provider platform evidence."""

    status: PlatformReconciliationStatus
    selected_platform: str | None = None
    local_platform: str | None = None
    provider_platform: str | None = None
    conflicts: tuple[str, ...] = ()

    @property
    def has_conflict(self) -> bool:
        return self.status is PlatformReconciliationStatus.CONFLICT


def reconcile_platform(
    detection: PlatformDetection,
    *,
    provider_platform: str | None = None,
) -> PlatformReconciliation:
    """Reconcile local platform inference with provider identification."""

    provider = (
        provider_platform.strip()
        if provider_platform is not None
        else None
    )

    if provider == "":
        provider = None

    best = detection.best

    if best is None:
        if provider is None:
            return PlatformReconciliation(
                status=PlatformReconciliationStatus.UNRESOLVED,
            )

        return PlatformReconciliation(
            status=PlatformReconciliationStatus.PROVIDER_ONLY,
            selected_platform=provider,
            provider_platform=provider,
        )

    local = best.platform

    if detection.is_ambiguous:
        top_confidence = best.confidence

        top_platforms = tuple(
            candidate.platform
            for candidate in detection.candidates
            if candidate.confidence == top_confidence
        )

        if provider is not None and provider in top_platforms:
            return PlatformReconciliation(
                status=PlatformReconciliationStatus.AGREEMENT,
                selected_platform=provider,
                local_platform=provider,
                provider_platform=provider,
            )

        return PlatformReconciliation(
            status=PlatformReconciliationStatus.AMBIGUOUS,
            selected_platform=provider,
            local_platform=None,
            provider_platform=provider,
        )

    if provider is None:
        return PlatformReconciliation(
            status=PlatformReconciliationStatus.LOCAL_ONLY,
            selected_platform=local,
            local_platform=local,
        )

    if local == provider:
        return PlatformReconciliation(
            status=PlatformReconciliationStatus.AGREEMENT,
            selected_platform=provider,
            local_platform=local,
            provider_platform=provider,
        )

    conflict = (
        "local platform evidence identifies "
        f"{local!r} but provider identity identifies {provider!r}"
    )

    return PlatformReconciliation(
        status=PlatformReconciliationStatus.CONFLICT,
        selected_platform=provider,
        local_platform=local,
        provider_platform=provider,
        conflicts=(conflict,),
    )
