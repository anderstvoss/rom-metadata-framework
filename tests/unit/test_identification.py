from pathlib import Path

from rom_metadata_framework.canonical import (
    CanonicalReleaseIdentity,
)
from rom_metadata_framework.content import (
    NormalizedContentIdentity,
)
from rom_metadata_framework.detection import (
    PlatformCandidate,
    PlatformDetection,
)
from rom_metadata_framework.identification import (
    IdentificationResult,
    identify_file,
)
from rom_metadata_framework.identity import HashSet


class FakeDetector:
    name = "fake"

    def __init__(
        self,
        platform: str | None,
    ) -> None:
        self.platform = platform

    def detect(
        self,
        path: Path,
    ) -> PlatformDetection:
        if self.platform is None:
            return PlatformDetection()

        return PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform=self.platform,
                    confidence=100,
                ),
            ),
        )


class FakeNormalizedResult:
    def __init__(
        self,
        content: NormalizedContentIdentity,
    ) -> None:
        self.content = content


class FakeNormalizer:
    def __init__(
        self,
        hashes: HashSet,
    ) -> None:
        self.hashes = hashes

    def identify(
        self,
        path: Path,
    ) -> FakeNormalizedResult:
        return FakeNormalizedResult(
            NormalizedContentIdentity(
                kind="cartridge",
                hashes=self.hashes,
            )
        )


class FakeResolver:
    def __init__(
        self,
        *,
        physical: CanonicalReleaseIdentity | None,
        normalized: CanonicalReleaseIdentity | None,
    ) -> None:
        self.physical = physical
        self.normalized = normalized

        self.identify_calls = 0
        self.lookup_calls = 0
        self.last_lookup = None

    def identify(
        self,
        identity,
    ):
        self.identify_calls += 1
        return self.physical

    def identify_lookup(
        self,
        lookup,
    ):
        self.lookup_calls += 1
        self.last_lookup = lookup
        return self.normalized


def release(
    *,
    platform: str = "nes",
) -> CanonicalReleaseIdentity:
    return CanonicalReleaseIdentity(
        release_name="Example Game (USA)",
        platform=platform,
        source="test",
        source_id="example",
    )


def test_physical_match_is_preferred(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.nes"
    path.write_bytes(b"physical-bytes")

    physical = release()
    normalized = release()

    resolver = FakeResolver(
        physical=physical,
        normalized=normalized,
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
        normalizer=FakeNormalizer(
            HashSet(
                sha1=(
                    "0123456789abcdef0123456789abcdef"
                    "01234567"
                ),
            )
        ),
    )

    assert result.physical_match is physical
    assert result.normalized_match is normalized
    assert result.canonical_match is physical
    assert result.physical_representation_matched
    assert result.normalized_content_matched
    assert not result.matched_via_normalization

    assert result.platform_reconciliation is not None
    assert (
        result.platform_reconciliation.status.value
        == "agreement"
    )


def test_normalized_match_is_fallback(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mutated.nes"
    path.write_bytes(b"physical-bytes")

    normalized = release()

    resolver = FakeResolver(
        physical=None,
        normalized=normalized,
    )

    normalized_hash = (
        "89abcdef0123456789abcdef01234567"
        "89abcdef"
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
        normalizer=FakeNormalizer(
            HashSet(
                sha1=normalized_hash,
            )
        ),
    )

    assert result.physical_match is None
    assert result.normalized_match is normalized
    assert result.canonical_match is normalized
    assert result.matched_via_normalization
    assert not result.physical_representation_matched
    assert result.normalized_content_matched

    assert resolver.last_lookup is not None
    assert (
        resolver.last_lookup.hashes.sha1
        == normalized_hash
    )


def test_provider_only_platform_from_normalized_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "headerless.bin"
    path.write_bytes(b"physical-bytes")

    resolver = FakeResolver(
        physical=None,
        normalized=release(
            platform="nes",
        ),
    )

    result = identify_file(
        path,
        detector=FakeDetector(None),
        resolver=resolver,
        normalizer=FakeNormalizer(
            HashSet(
                sha1=(
                    "0123456789abcdef0123456789abcdef"
                    "01234567"
                ),
            )
        ),
    )

    assert result.platform_reconciliation is not None
    assert (
        result.platform_reconciliation.status.value
        == "provider_only"
    )
    assert (
        result.platform_reconciliation.selected_platform
        == "nes"
    )


def test_platform_conflict_is_preserved(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.bin"
    path.write_bytes(b"physical-bytes")

    resolver = FakeResolver(
        physical=release(
            platform="wii",
        ),
        normalized=None,
    )

    result = identify_file(
        path,
        detector=FakeDetector("gamecube"),
        resolver=resolver,
    )

    assert result.platform_reconciliation is not None
    assert (
        result.platform_reconciliation.status.value
        == "conflict"
    )
    assert result.platform_reconciliation.has_conflict


def test_normalizer_is_optional(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.bin"
    path.write_bytes(b"physical-bytes")

    resolver = FakeResolver(
        physical=None,
        normalized=None,
    )

    result = identify_file(
        path,
        detector=FakeDetector(None),
        resolver=resolver,
    )

    assert isinstance(
        result,
        IdentificationResult,
    )
    assert result.normalized_content is None
    assert result.normalized_match is None
    assert result.canonical_match is None

    assert resolver.identify_calls == 1
    assert resolver.lookup_calls == 0

    assert result.platform_reconciliation is not None
    assert (
        result.platform_reconciliation.status.value
        == "unresolved"
    )


def verified_release(
    *,
    authority: str,
    status: str | None,
    platform: str = "nes",
) -> CanonicalReleaseIdentity:
    from rom_metadata_framework.provenance import (
        CatalogueEvidence,
    )

    return CanonicalReleaseIdentity(
        release_name="Example Game (USA)",
        platform=platform,
        source="test",
        source_id="example",
        catalogue_evidence=(
            CatalogueEvidence(
                source="test",
                match_method="SHA1",
                authority=authority,
                catalogue_name="Example Catalogue",
                file_status=status,
                current_in_latest_catalogue=True,
            ),
        ),
    )


def test_identification_verification_separates_representation_and_content(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.identification import (
        verify_identification,
    )

    path = tmp_path / "mutated.nes"
    path.write_bytes(b"physical-bytes")

    normalized = verified_release(
        authority="No-Intro",
        status="Verified",
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=None,
            normalized=normalized,
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=(
                    "0123456789abcdef0123456789abcdef"
                    "01234567"
                ),
            )
        ),
    )

    report = verify_identification(result)

    assert report.physical is None
    assert report.normalized is not None
    assert report.normalized_known_good
    assert report.content_known_good
    assert not report.physical_known_good
    assert not report.representation_known_good


def test_identification_verification_tracks_both_known_good_layers(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.identification import (
        verify_identification,
    )

    path = tmp_path / "canonical.nes"
    path.write_bytes(b"physical-bytes")

    physical = verified_release(
        authority="No-Intro",
        status="Verified",
    )
    normalized = verified_release(
        authority="No-Intro",
        status="Verified",
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=physical,
            normalized=normalized,
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=(
                    "0123456789abcdef0123456789abcdef"
                    "01234567"
                ),
            )
        ),
    )

    report = verify_identification(result)

    assert report.physical_known_good
    assert report.normalized_known_good
    assert report.content_known_good
    assert report.representation_known_good


def test_redump_normalized_content_can_be_known_good(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.identification import (
        verify_identification,
    )

    path = tmp_path / "disc.rvz"
    path.write_bytes(b"physical-container")

    normalized = verified_release(
        authority="Redump",
        status=None,
        platform="gamecube",
    )

    result = identify_file(
        path,
        detector=FakeDetector("gamecube"),
        resolver=FakeResolver(
            physical=None,
            normalized=normalized,
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=(
                    "0123456789abcdef0123456789abcdef"
                    "01234567"
                ),
            )
        ),
    )

    report = verify_identification(result)

    assert report.physical is None
    assert report.normalized_known_good
    assert report.content_known_good
    assert not report.representation_known_good
