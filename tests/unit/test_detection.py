from pathlib import Path

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

    assert candidate.platform == "gba"


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


def test_composite_platform_detector_combines_independent_evidence(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.detection import (
        CompositePlatformDetector,
        PlatformCandidate,
        PlatformDetection,
        PlatformEvidence,
    )

    class Detector:
        def __init__(
            self,
            name: str,
            platform: str,
            confidence: int,
        ) -> None:
            self.name = name
            self.platform = platform
            self.confidence = confidence

        def detect(self, path: Path) -> PlatformDetection:
            return PlatformDetection(
                candidates=(
                    PlatformCandidate(
                        platform=self.platform,
                        confidence=self.confidence,
                        evidence=(
                            PlatformEvidence(
                                source=self.name,
                                method="test",
                                value=self.platform,
                                strength=self.confidence,
                            ),
                        ),
                    ),
                ),
            )

    path = tmp_path / "example.bin"
    path.write_bytes(b"example")

    detection = CompositePlatformDetector(
        (
            Detector("one", "nes", 90),
            Detector("two", "xbox", 80),
        )
    ).detect(path)

    assert tuple(candidate.platform for candidate in detection.candidates) == (
        "nes",
        "xbox",
    )
    assert detection.best is not None
    assert detection.best.platform == "nes"


def test_composite_platform_detector_merges_same_platform_evidence(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.detection import (
        CompositePlatformDetector,
        PlatformCandidate,
        PlatformDetection,
        PlatformEvidence,
    )

    class Detector:
        def __init__(self, name: str, confidence: int) -> None:
            self.name = name
            self.confidence = confidence

        def detect(self, path: Path) -> PlatformDetection:
            return PlatformDetection(
                candidates=(
                    PlatformCandidate(
                        platform="nes",
                        confidence=self.confidence,
                        evidence=(
                            PlatformEvidence(
                                source=self.name,
                                method="test",
                                value="nes",
                                strength=self.confidence,
                            ),
                        ),
                    ),
                ),
            )

    path = tmp_path / "example.bin"
    path.write_bytes(b"example")

    detection = CompositePlatformDetector(
        (
            Detector("one", 70),
            Detector("two", 95),
        )
    ).detect(path)

    assert len(detection.candidates) == 1
    candidate = detection.candidates[0]
    assert candidate.platform == "nes"
    assert candidate.confidence == 95
    assert tuple(evidence.source for evidence in candidate.evidence) == ("one", "two")
