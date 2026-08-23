import pytest

from rom_metadata_framework.detection import (
    PlatformCandidate,
    PlatformDetection,
    PlatformEvidence,
)


def test_platform_evidence_normalizes_fields() -> None:
    evidence = PlatformEvidence(
        source=" Internal Header ",
        method=" Magic ",
        value=" 0x24ffae51699aa221 ",
        strength=95,
        details={" offset ": " 4 "},
    )

    assert evidence.source == "internal header"
    assert evidence.method == "magic"
    assert evidence.value == "0x24ffae51699aa221"
    assert evidence.details == {"offset": "4"}


def test_platform_candidate_uses_canonical_registry() -> None:
    candidate = PlatformCandidate(
        platform="GBA",
        confidence=95,
    )

    assert candidate.platform == "game-boy-advance"


def test_detection_returns_highest_confidence_candidate() -> None:
    detection = PlatformDetection(
        candidates=(
            PlatformCandidate(
                platform="snes",
                confidence=90,
            ),
            PlatformCandidate(
                platform="genesis",
                confidence=20,
            ),
        )
    )

    assert detection.best is not None
    assert detection.best.platform == "snes"


def test_detection_can_be_unknown() -> None:
    detection = PlatformDetection()

    assert detection.best is None
    assert not detection.is_ambiguous


def test_detection_reports_equal_top_candidates_as_ambiguous() -> None:
    detection = PlatformDetection(
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

    assert detection.is_ambiguous


@pytest.mark.parametrize("strength", [-1, 101])
def test_platform_evidence_rejects_invalid_strength(
    strength: int,
) -> None:
    with pytest.raises(ValueError):
        PlatformEvidence(
            source="test",
            method="magic",
            value="value",
            strength=strength,
        )


@pytest.mark.parametrize("confidence", [-1, 101])
def test_platform_candidate_rejects_invalid_confidence(
    confidence: int,
) -> None:
    with pytest.raises(ValueError):
        PlatformCandidate(
            platform="snes",
            confidence=confidence,
        )
