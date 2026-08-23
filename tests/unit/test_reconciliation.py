from rom_metadata_framework.detection import (
    PlatformCandidate,
    PlatformDetection,
)
from rom_metadata_framework.reconciliation import (
    PlatformReconciliationStatus,
    reconcile_platform,
)


def detection(
    platform: str,
    confidence: int = 90,
) -> PlatformDetection:
    return PlatformDetection(
        candidates=(
            PlatformCandidate(
                platform=platform,
                confidence=confidence,
            ),
        )
    )


def test_no_evidence_is_unresolved() -> None:
    result = reconcile_platform(PlatformDetection())

    assert result.status is PlatformReconciliationStatus.UNRESOLVED
    assert result.selected_platform is None


def test_provider_can_establish_platform_when_local_unknown() -> None:
    result = reconcile_platform(
        PlatformDetection(),
        provider_platform="snes",
    )

    assert result.status is PlatformReconciliationStatus.PROVIDER_ONLY
    assert result.selected_platform == "snes"
    assert result.local_platform is None
    assert result.provider_platform == "snes"


def test_local_detector_can_establish_platform_without_provider() -> None:
    result = reconcile_platform(detection("snes"))

    assert result.status is PlatformReconciliationStatus.LOCAL_ONLY
    assert result.selected_platform == "snes"
    assert result.local_platform == "snes"
    assert result.provider_platform is None


def test_matching_local_and_provider_evidence_agree() -> None:
    result = reconcile_platform(
        detection("snes"),
        provider_platform="snes",
    )

    assert result.status is PlatformReconciliationStatus.AGREEMENT
    assert result.selected_platform == "snes"
    assert not result.has_conflict


def test_disagreement_is_explicit_conflict() -> None:
    result = reconcile_platform(
        detection("snes"),
        provider_platform="genesis",
    )

    assert result.status is PlatformReconciliationStatus.CONFLICT
    assert result.selected_platform == "genesis"
    assert result.local_platform == "snes"
    assert result.provider_platform == "genesis"
    assert result.has_conflict
    assert result.conflicts


def test_equal_local_candidates_are_ambiguous() -> None:
    result = reconcile_platform(
        PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform="snes",
                    confidence=80,
                ),
                PlatformCandidate(
                    platform="genesis",
                    confidence=80,
                ),
            )
        )
    )

    assert result.status is PlatformReconciliationStatus.AMBIGUOUS
    assert result.selected_platform is None


def test_provider_can_resolve_equal_local_candidates() -> None:
    result = reconcile_platform(
        PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform="snes",
                    confidence=80,
                ),
                PlatformCandidate(
                    platform="genesis",
                    confidence=80,
                ),
            )
        ),
        provider_platform="snes",
    )

    assert result.status is PlatformReconciliationStatus.AGREEMENT
    assert result.selected_platform == "snes"


def test_provider_does_not_hide_unrelated_local_ambiguity() -> None:
    result = reconcile_platform(
        PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform="snes",
                    confidence=80,
                ),
                PlatformCandidate(
                    platform="genesis",
                    confidence=80,
                ),
            )
        ),
        provider_platform="nes",
    )

    assert result.status is PlatformReconciliationStatus.AMBIGUOUS
    assert result.selected_platform == "nes"
