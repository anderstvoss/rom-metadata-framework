from pathlib import Path

from rom_metadata_framework.canonical import (
    CanonicalReleaseIdentity,
)
from rom_metadata_framework.content import (
    NormalizedContentIdentity,
)
from rom_metadata_framework.contracts import NormalizerContractError
from rom_metadata_framework.detection import (
    PlatformCandidate,
    PlatformDetection,
)
from rom_metadata_framework.identification import (
    IdentificationResult,
    IdentificationStrength,
    IdentificationTitleSource,
    ProviderLookupStatus,
    identify_file,
)
from rom_metadata_framework.identity import HashSet, RomIdentity
from rom_metadata_framework.resolvers import (
    ResolverUnavailableError,
)


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
        self.local_metadata = None
        self.physical_representation = None


class FakeNormalizer:
    def __init__(
        self,
        hashes: HashSet,
    ) -> None:
        self.hashes = hashes
        self.identify_calls = 0

    def identify(
        self,
        path: Path,
    ) -> FakeNormalizedResult:
        self.identify_calls += 1

        return FakeNormalizedResult(
            NormalizedContentIdentity(
                kind="cartridge",
                hashes=self.hashes,
            )
        )


class FakeResolver:
    name = "fake"

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
    release_name: str = "Example Game (USA)",
    source: str = "test",
    source_id: str = "example",
) -> CanonicalReleaseIdentity:
    return CanonicalReleaseIdentity(
        release_name=release_name,
        platform=platform,
        source=source,
        source_id=source_id,
    )


def authoritative_release(
    *,
    platform: str = "nes",
    release_name: str = "Example Game (USA)",
) -> CanonicalReleaseIdentity:
    from rom_metadata_framework.canonical import (
        IdentificationEvidence,
    )

    return CanonicalReleaseIdentity(
        release_name=release_name,
        platform=platform,
        source="test",
        source_id="authoritative",
        evidence=(
            IdentificationEvidence(
                source="test",
                method="SHA1",
                authoritative=True,
            ),
        ),
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
                sha1=("0123456789abcdef0123456789abcdef01234567"),
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
    assert result.platform_reconciliation.status.value == "agreement"


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

    normalized_hash = "89abcdef0123456789abcdef0123456789abcdef"

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
    assert resolver.last_lookup.hashes.sha1 == normalized_hash



def test_physical_provider_unavailable_preserves_local_workflow(
    tmp_path: Path,
) -> None:
    path = tmp_path / "local-only.bin"
    path.write_bytes(b"physical-bytes")

    class UnavailableResolver(FakeResolver):
        def identify(self, identity):
            self.identify_calls += 1

            raise ResolverUnavailableError(
                "provider unavailable"
            )

    resolver = UnavailableResolver(
        physical=None,
        normalized=None,
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
    )

    assert result.physical_match is None
    assert result.canonical_match is None

    assert result.platform_detection.best is not None
    assert (
        result.platform_detection.best.platform
        == "nes"
    )

    assert (
        result.physical_lookup.status
        is ProviderLookupStatus.UNAVAILABLE
    )
    assert (
        result.physical_lookup.reason
        == "provider unavailable"
    )
    assert (
        result.normalized_lookup.status
        is ProviderLookupStatus.NOT_ATTEMPTED
    )

    assert result.provider_unavailable
    assert result.provider_name == "fake"


def test_normalized_provider_unavailable_preserves_content_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "normalized.bin"
    path.write_bytes(b"physical-bytes")

    class NormalizedUnavailableResolver(FakeResolver):
        def identify_lookup(self, lookup):
            self.lookup_calls += 1
            self.last_lookup = lookup

            raise ResolverUnavailableError(
                "normalized lookup unavailable"
            )

    resolver = NormalizedUnavailableResolver(
        physical=None,
        normalized=None,
    )

    normalized_hash = (
        "89abcdef0123456789abcdef"
        "0123456789abcdef"
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

    assert result.normalized_content is not None
    assert (
        result.normalized_content.hashes.sha1
        == normalized_hash
    )

    assert (
        result.physical_lookup.status
        is ProviderLookupStatus.NO_MATCH
    )
    assert (
        result.normalized_lookup.status
        is ProviderLookupStatus.UNAVAILABLE
    )
    assert (
        result.normalized_lookup.reason
        == "normalized lookup unavailable"
    )

    assert result.provider_unavailable


def test_lookup_outcomes_distinguish_match_and_no_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "matched.nes"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=release(),
            normalized=None,
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

    assert (
        result.physical_lookup.status
        is ProviderLookupStatus.MATCHED
    )
    assert (
        result.normalized_lookup.status
        is ProviderLookupStatus.NO_MATCH
    )

    assert not result.provider_unavailable



def test_lookup_outcome_not_attempted_is_not_available() -> None:
    from rom_metadata_framework.identification import (
        ProviderLookupOutcome,
    )

    outcome = ProviderLookupOutcome()

    assert not outcome.attempted
    assert not outcome.available


def test_catalogue_match_has_catalogue_strength_and_title(
    tmp_path: Path,
) -> None:
    path = tmp_path / "catalogued.nes"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=release(
                release_name="Canonical Game (USA)",
            ),
            normalized=None,
        ),
    )

    assert (
        result.identification_strength
        is IdentificationStrength.CATALOGUE
    )
    assert (
        result.title_source
        is IdentificationTitleSource.CATALOGUE
    )
    assert result.display_title == "Canonical Game (USA)"


def test_native_identifier_produces_strong_local_identification(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.inspection import (
        StructuralInspectionResult,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )

    class LocalInspector:
        def inspect(self, path: Path):
            provenance = LocalMetadataProvenance(
                source="synthetic",
                method="disc-header",
            )

            return StructuralInspectionResult(
                local_metadata=LocalContentMetadata(
                    platform="wii",
                    titles=(
                        LocalMetadataValue(
                            value="INTERNAL GAME NAME",
                            provenance=provenance,
                        ),
                    ),
                    identifiers=(
                        LocalIdentifier(
                            namespace="nintendo-game-id",
                            value="ABCE01",
                            provenance=provenance,
                        ),
                    ),
                )
            )

    class UnavailableResolver(FakeResolver):
        def identify(self, identity):
            self.identify_calls += 1
            raise ResolverUnavailableError(
                "provider unavailable"
            )

    path = tmp_path / "local.rvz"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("wii"),
        resolver=UnavailableResolver(
            physical=None,
            normalized=None,
        ),
        inspector=LocalInspector(),
    )

    assert result.canonical_match is None
    assert (
        result.identification_strength
        is IdentificationStrength.LOCAL_STRONG
    )
    assert (
        result.title_source
        is IdentificationTitleSource.EMBEDDED
    )
    assert result.display_title == "INTERNAL GAME NAME"
    assert result.provider_unavailable


def test_embedded_metadata_without_identifier_is_local_probable(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.inspection import (
        StructuralInspectionResult,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )

    class LocalInspector:
        def inspect(self, path: Path):
            provenance = LocalMetadataProvenance(
                source="synthetic",
                method="header",
            )

            return StructuralInspectionResult(
                local_metadata=LocalContentMetadata(
                    platform="nes",
                    titles=(
                        LocalMetadataValue(
                            value="Embedded Game",
                            provenance=provenance,
                        ),
                    ),
                )
            )

    path = tmp_path / "probable.bin"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=None,
            normalized=None,
        ),
        inspector=LocalInspector(),
    )

    assert (
        result.identification_strength
        is IdentificationStrength.LOCAL_PROBABLE
    )
    assert (
        result.title_source
        is IdentificationTitleSource.EMBEDDED
    )
    assert result.display_title == "Embedded Game"


def test_platform_detection_without_metadata_is_local_probable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "detected.bin"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=None,
            normalized=None,
        ),
    )

    assert (
        result.identification_strength
        is IdentificationStrength.LOCAL_PROBABLE
    )
    assert (
        result.title_source
        is IdentificationTitleSource.UNAVAILABLE
    )
    assert result.display_title is None


def test_no_provider_or_local_evidence_is_unresolved(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unknown.bin"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector(None),
        resolver=FakeResolver(
            physical=None,
            normalized=None,
        ),
    )

    assert (
        result.identification_strength
        is IdentificationStrength.UNRESOLVED
    )
    assert (
        result.title_source
        is IdentificationTitleSource.UNAVAILABLE
    )
    assert result.display_title is None


def test_authoritative_physical_match_skips_normalization(
    tmp_path: Path,
) -> None:
    path = tmp_path / "authoritative.nes"
    path.write_bytes(b"physical-bytes")

    physical = authoritative_release()

    normalizer = FakeNormalizer(
        HashSet(
            sha1=(
                "0123456789abcdef0123456789abcdef"
                "01234567"
            ),
        )
    )

    resolver = FakeResolver(
        physical=physical,
        normalized=release(),
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
        normalizer=normalizer,
    )

    assert result.physical_match is physical
    assert result.normalized_content is None
    assert result.normalized_match is None

    assert normalizer.identify_calls == 0
    assert resolver.lookup_calls == 0

    assert (
        result.normalized_lookup.status
        is ProviderLookupStatus.NOT_ATTEMPTED
    )


def test_force_normalization_overrides_authoritative_skip(
    tmp_path: Path,
) -> None:
    path = tmp_path / "authoritative-forced.nes"
    path.write_bytes(b"physical-bytes")

    normalized = release()

    normalizer = FakeNormalizer(
        HashSet(
            sha1=(
                "0123456789abcdef0123456789abcdef"
                "01234567"
            ),
        )
    )

    resolver = FakeResolver(
        physical=authoritative_release(),
        normalized=normalized,
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
        normalizer=normalizer,
        force_normalization=True,
    )

    assert normalizer.identify_calls == 1
    assert resolver.lookup_calls == 1

    assert result.normalized_content is not None
    assert result.normalized_match is normalized

    assert (
        result.normalized_lookup.status
        is ProviderLookupStatus.MATCHED
    )


def test_non_authoritative_physical_match_still_normalizes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "weak.nes"
    path.write_bytes(b"physical-bytes")

    normalizer = FakeNormalizer(
        HashSet(
            sha1=(
                "0123456789abcdef0123456789abcdef"
                "01234567"
            ),
        )
    )

    resolver = FakeResolver(
        physical=release(),
        normalized=None,
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
        normalizer=normalizer,
    )

    assert normalizer.identify_calls == 1
    assert resolver.lookup_calls == 1

    assert (
        result.physical_lookup.status
        is ProviderLookupStatus.MATCHED
    )
    assert (
        result.normalized_lookup.status
        is ProviderLookupStatus.NO_MATCH
    )


def test_provider_unavailable_skips_normalization_by_default(
    tmp_path: Path,
) -> None:
    class UnavailableResolver(FakeResolver):
        def identify(self, identity):
            self.identify_calls += 1

            raise ResolverUnavailableError(
                "provider offline"
            )

    path = tmp_path / "offline.nes"
    path.write_bytes(b"physical-bytes")

    normalizer = FakeNormalizer(
        HashSet(
            sha1=(
                "0123456789abcdef0123456789abcdef"
                "01234567"
            ),
        )
    )

    resolver = UnavailableResolver(
        physical=None,
        normalized=release(),
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
        normalizer=normalizer,
    )

    assert result.provider_unavailable

    assert normalizer.identify_calls == 0
    assert resolver.lookup_calls == 0
    assert result.normalized_content is None

    assert (
        result.normalized_lookup.status
        is ProviderLookupStatus.NOT_ATTEMPTED
    )


def test_force_normalization_after_physical_provider_unavailable(
    tmp_path: Path,
) -> None:
    class PhysicalUnavailableResolver(FakeResolver):
        def identify(self, identity):
            self.identify_calls += 1

            raise ResolverUnavailableError(
                "physical provider offline"
            )

    path = tmp_path / "offline-forced.nes"
    path.write_bytes(b"physical-bytes")

    normalized = release()

    normalizer = FakeNormalizer(
        HashSet(
            sha1=(
                "0123456789abcdef0123456789abcdef"
                "01234567"
            ),
        )
    )

    resolver = PhysicalUnavailableResolver(
        physical=None,
        normalized=normalized,
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
        normalizer=normalizer,
        force_normalization=True,
    )

    assert normalizer.identify_calls == 1
    assert resolver.lookup_calls == 1

    assert (
        result.physical_lookup.status
        is ProviderLookupStatus.UNAVAILABLE
    )
    assert (
        result.normalized_lookup.status
        is ProviderLookupStatus.MATCHED
    )

    assert result.normalized_match is normalized


def test_authoritative_platform_conflict_still_normalizes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "platform-conflict.bin"
    path.write_bytes(b"physical-bytes")

    normalizer = FakeNormalizer(
        HashSet(
            sha1=(
                "0123456789abcdef0123456789abcdef"
                "01234567"
            ),
        )
    )

    resolver = FakeResolver(
        physical=authoritative_release(
            platform="nes",
        ),
        normalized=None,
    )

    result = identify_file(
        path,
        detector=FakeDetector("snes"),
        resolver=resolver,
        normalizer=normalizer,
    )

    assert normalizer.identify_calls == 1
    assert resolver.lookup_calls == 1

    assert result.platform_reconciliation is not None
    assert result.has_platform_conflict


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
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    assert result.platform_reconciliation is not None
    assert result.platform_reconciliation.status.value == "provider_only"
    assert result.platform_reconciliation.selected_platform == "nes"


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
        detector=FakeDetector("gc"),
        resolver=resolver,
    )

    assert result.platform_reconciliation is not None
    assert result.platform_reconciliation.status.value == "conflict"
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
    assert result.platform_reconciliation.status.value == "unresolved"


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
                sha1=("0123456789abcdef0123456789abcdef01234567"),
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
                sha1=("0123456789abcdef0123456789abcdef01234567"),
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
        platform="gc",
    )

    result = identify_file(
        path,
        detector=FakeDetector("gc"),
        resolver=FakeResolver(
            physical=None,
            normalized=normalized,
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    report = verify_identification(result)

    assert report.physical is None
    assert report.normalized_known_good
    assert report.content_known_good
    assert not report.representation_known_good


def test_identification_skips_normalized_lookup_when_router_has_no_match(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.routing import (
        CompositeNormalizer,
    )

    class UnsupportedNormalizer:
        name = "unsupported"

        def runtime_capability(self):
            from rom_metadata_framework.capability import (
                RuntimeCapability,
                RuntimeCapabilityStatus,
            )

            return RuntimeCapability(
                name="unsupported-normalization",
                status=RuntimeCapabilityStatus.READY,
            )

        def probe(self, path: Path):
            from rom_metadata_framework.normalization import (
                NormalizerProbe,
                NormalizerProbeStatus,
            )

            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSUPPORTED,
            )

        def identify(self, path: Path):
            raise AssertionError("unsupported normalizer must not identify")

    path = tmp_path / "unknown.bin"
    path.write_bytes(b"unknown-content")

    detector = FakeDetector(None)
    resolver = FakeResolver(
        physical=None,
        normalized=None,
    )

    result = identify_file(
        path,
        detector=detector,
        resolver=resolver,
        normalizer=CompositeNormalizer((UnsupportedNormalizer(),)),
    )

    assert result.normalized_content is None
    assert result.normalized_match is None


def test_identification_propagates_ambiguous_normalizer(
    tmp_path: Path,
) -> None:
    import pytest

    from rom_metadata_framework.routing import (
        AmbiguousNormalizerError,
        CompositeNormalizer,
    )

    class ClaimingNormalizer:
        def __init__(self, name: str) -> None:
            self.name = name
            self.identify_calls = 0

        def runtime_capability(self):
            from rom_metadata_framework.capability import (
                RuntimeCapability,
                RuntimeCapabilityStatus,
            )

            return RuntimeCapability(
                name=f"{self.name}-normalization",
                status=RuntimeCapabilityStatus.READY,
            )

        def probe(self, path: Path):
            from rom_metadata_framework.normalization import (
                NormalizerProbe,
                NormalizerProbeStatus,
            )

            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.SUPPORTED,
            )

        def identify(self, path: Path):
            self.identify_calls += 1
            raise AssertionError("ambiguous normalizer must not identify")

    path = tmp_path / "ambiguous.bin"
    path.write_bytes(b"ambiguous-content")

    first = ClaimingNormalizer("first")
    second = ClaimingNormalizer("second")

    resolver = FakeResolver(
        physical=None,
        normalized=None,
    )

    with pytest.raises(
        AmbiguousNormalizerError,
    ) as exc_info:
        identify_file(
            path,
            detector=FakeDetector(None),
            resolver=resolver,
            normalizer=CompositeNormalizer((first, second)),
        )

    assert exc_info.value.adapter_names == (
        "first",
        "second",
    )

    # Physical provider lookup still occurs first.
    assert resolver.identify_calls == 1

    # Ambiguous routing must not invoke either normalizer.
    assert first.identify_calls == 0
    assert second.identify_calls == 0

    # No normalized provider lookup can occur.
    assert resolver.lookup_calls == 0


def test_identification_propagates_terminal_normalizer_probe_failure(
    tmp_path: Path,
) -> None:
    import pytest

    from rom_metadata_framework.normalization import (
        NormalizerProbe,
        NormalizerProbeStatus,
    )
    from rom_metadata_framework.routing import (
        CompositeNormalizer,
        NormalizerProbeFailureError,
    )

    class FailedNormalizer:
        name = "failed"

        def probe(self, path: Path) -> NormalizerProbe:
            return NormalizerProbe(
                normalizer=self.name,
                status=(NormalizerProbeStatus.BACKEND_UNAVAILABLE),
                reason="backend unavailable",
            )

        def runtime_capability(self):
            from rom_metadata_framework.capability import (
                RuntimeCapability,
                RuntimeCapabilityStatus,
            )

            return RuntimeCapability(
                name="failed-normalization",
                status=RuntimeCapabilityStatus.UNAVAILABLE,
                reason="backend unavailable",
            )

        def identify(self, path: Path):
            raise AssertionError("failed normalizer must not identify")

    path = tmp_path / "source.bin"
    path.write_bytes(b"source")

    resolver = FakeResolver(
        physical=None,
        normalized=None,
    )

    with pytest.raises(
        NormalizerProbeFailureError,
    ):
        identify_file(
            path,
            detector=FakeDetector(None),
            resolver=resolver,
            normalizer=CompositeNormalizer((FailedNormalizer(),)),
        )

    # Physical provider lookup remains provider-first.
    assert resolver.identify_calls == 1

    # No normalized provider lookup can occur.
    assert resolver.lookup_calls == 0


def test_identification_reconciles_same_release_from_different_records(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.nes"
    path.write_bytes(b"physical-bytes")

    physical = release(
        source="headered-catalogue",
        source_id="physical-record",
    )
    normalized = release(
        source="headerless-catalogue",
        source_id="normalized-record",
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
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    assert result.release_reconciliation is not None
    assert result.release_reconciliation.status.value == "agreement"
    assert result.canonical_match is physical


def test_provider_release_conflict_blocks_canonical_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "conflict.nes"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=release(
                release_name="Game A (USA)",
            ),
            normalized=release(
                release_name="Game B (USA)",
            ),
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    assert result.release_reconciliation is not None
    assert result.release_reconciliation.status.value == "release_conflict"
    assert result.release_reconciliation.has_conflict
    assert result.canonical_match is None

    assert result.platform_reconciliation is not None
    assert result.platform_reconciliation.status.value == "agreement"


def test_provider_platform_conflict_blocks_canonical_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "platform-conflict.bin"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=release(platform="nes"),
            normalized=release(platform="snes"),
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    assert result.release_reconciliation is not None
    assert result.release_reconciliation.status.value == "platform_conflict"
    assert result.release_reconciliation.has_conflict
    assert result.canonical_match is None

    assert result.platform_reconciliation is not None
    assert result.platform_reconciliation.status.value == "local_only"


def test_normalized_only_release_reconciliation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "normalized-only.nes"
    path.write_bytes(b"physical-bytes")

    normalized = release()

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=None,
            normalized=normalized,
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    assert result.release_reconciliation is not None
    assert result.release_reconciliation.status.value == "normalized_only"
    assert result.canonical_match is normalized


def bad_release(
    *,
    platform: str = "nes",
    release_name: str = "Example Game (USA)",
) -> CanonicalReleaseIdentity:
    from rom_metadata_framework.provenance import CatalogueEvidence

    return CanonicalReleaseIdentity(
        release_name=release_name,
        platform=platform,
        source="bad-catalogue",
        source_id="bad-record",
        catalogue_evidence=(
            CatalogueEvidence(
                source="bad-catalogue",
                match_method="SHA1",
                authority="Example",
                catalogue_name="Example Bad DAT",
                file_status="Bad",
                current_in_latest_catalogue=True,
            ),
        ),
    )


def test_known_bad_physical_vetoes_known_good_normalized_naming(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.identification import verify_identification

    path = tmp_path / "mixed-verification.nes"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=bad_release(),
            normalized=verified_release(
                authority="No-Intro",
                status="Verified",
            ),
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    verification = verify_identification(result)

    assert verification.physical is not None
    assert verification.normalized is not None
    assert verification.physical.status.value == "known_bad"
    assert verification.normalized_known_good
    assert verification.content_known_good
    assert verification.has_known_bad
    assert not verification.safe_for_canonical_naming


def test_known_bad_normalized_vetoes_known_good_physical_naming(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.identification import verify_identification

    path = tmp_path / "mixed-verification-reverse.nes"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=FakeResolver(
            physical=verified_release(
                authority="No-Intro",
                status="Verified",
            ),
            normalized=bad_release(),
        ),
        normalizer=FakeNormalizer(
            HashSet(
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    verification = verify_identification(result)

    assert verification.physical_known_good
    assert verification.normalized is not None
    assert verification.normalized.status.value == "known_bad"
    assert verification.content_known_good
    assert verification.has_known_bad
    assert not verification.safe_for_canonical_naming


def test_release_conflict_vetoes_known_good_naming(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.identification import verify_identification

    path = tmp_path / "release-conflict-verified.nes"
    path.write_bytes(b"physical-bytes")

    physical = verified_release(
        authority="No-Intro",
        status="Verified",
    )

    normalized = CanonicalReleaseIdentity(
        release_name="Different Game (USA)",
        platform="nes",
        source="other",
        source_id="other-record",
        catalogue_evidence=physical.catalogue_evidence,
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
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    verification = verify_identification(result)

    assert verification.physical_known_good
    assert verification.normalized_known_good
    assert verification.content_known_good
    assert verification.has_conflicts
    assert not verification.safe_for_canonical_naming
    assert result.canonical_match is None


def test_agreeing_known_good_paths_remain_safe_for_naming(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.identification import verify_identification

    path = tmp_path / "agreement-verified.nes"
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
                sha1=("0123456789abcdef0123456789abcdef01234567"),
            )
        ),
    )

    verification = verify_identification(result)

    assert verification.content_known_good
    assert not verification.has_known_bad
    assert not verification.has_conflicts
    assert verification.safe_for_canonical_naming


def test_identification_preserves_normalizer_local_metadata(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
    )

    class MetadataResult:
        def __init__(
            self,
            content: NormalizedContentIdentity,
            local_metadata: LocalContentMetadata,
        ) -> None:
            self.content = content
            self.local_metadata = local_metadata
            self.physical_representation = None

    class MetadataNormalizer:
        def identify(
            self,
            path: Path,
        ) -> MetadataResult:
            return MetadataResult(
                NormalizedContentIdentity(
                    kind="cartridge",
                    hashes=HashSet(
                        sha1=("0123456789abcdef0123456789abcdef01234567"),
                    ),
                ),
                LocalContentMetadata(
                    platform="nes",
                    hardware={
                        "mapper": "4",
                    },
                ),
            )

    path = tmp_path / "game.nes"
    path.write_bytes(b"physical-bytes")

    resolver = FakeResolver(
        physical=None,
        normalized=None,
    )

    result = identify_file(
        path,
        detector=FakeDetector("nes"),
        resolver=resolver,
        normalizer=MetadataNormalizer(),
    )

    assert result.local_metadata is not None
    assert result.local_metadata.platform == "nes"
    assert result.local_metadata.hardware["mapper"] == "4"

    # Local metadata does not change provider lookup behavior.
    assert resolver.identify_calls == 1
    assert resolver.lookup_calls == 1


def test_identification_without_normalizer_has_no_local_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "physical.bin"
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

    assert result.local_metadata is None
    assert resolver.identify_calls == 1
    assert resolver.lookup_calls == 0


def test_identification_rejects_invalid_local_metadata_result(
    tmp_path: Path,
) -> None:
    import pytest

    class InvalidMetadataResult:
        def __init__(self) -> None:
            self.content = NormalizedContentIdentity(
                kind="cartridge",
            )
            self.local_metadata = {
                "platform": "nes",
            }
            self.physical_representation = None

    class InvalidMetadataNormalizer:
        def identify(
            self,
            path: Path,
        ) -> InvalidMetadataResult:
            return InvalidMetadataResult()

    path = tmp_path / "invalid.bin"
    path.write_bytes(b"physical-bytes")

    resolver = FakeResolver(
        physical=None,
        normalized=None,
    )

    with pytest.raises(
        NormalizerContractError,
        match="normalizer local_metadata",
    ):
        identify_file(
            path,
            detector=FakeDetector(None),
            resolver=resolver,
            normalizer=InvalidMetadataNormalizer(),
        )

    # Physical lookup must still have happened before normalization.
    assert resolver.identify_calls == 1

    # Invalid local evidence prevents normalized lookup.
    assert resolver.lookup_calls == 0


def test_identification_preserves_normalizer_representation(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.representation import (
        RepresentationIdentity,
    )

    path = tmp_path / "example.rvz"
    path.write_bytes(b"physical-container")

    representation = RepresentationIdentity(
        kind="disc-image",
        format="rvz",
        metadata={
            "compression_method": "Zstandard",
        },
    )

    class RepresentationNormalizer:
        def identify(self, path: Path):
            class Result:
                content = NormalizedContentIdentity(
                    kind="disc",
                )
                local_metadata = None
                physical_representation = representation

            return Result()

    result = identify_file(
        path,
        detector=FakeDetector("gc"),
        resolver=FakeResolver(
            physical=None,
            normalized=None,
        ),
        normalizer=RepresentationNormalizer(),
    )

    assert result.physical_representation is representation
    assert result.physical_representation.kind == "disc-image"
    assert result.physical_representation.format == "rvz"
    assert result.physical_representation.metadata == {
        "compression_method": "Zstandard",
    }


def test_identification_rejects_incomplete_normalizer_result(
    tmp_path: Path,
) -> None:
    import pytest

    class IncompleteResult:
        content = NormalizedContentIdentity(
            kind="cartridge",
        )

    class IncompleteNormalizer:
        def identify(
            self,
            path: Path,
        ) -> IncompleteResult:
            return IncompleteResult()

    path = tmp_path / "incomplete.bin"
    path.write_bytes(b"physical-bytes")

    resolver = FakeResolver(
        physical=None,
        normalized=None,
    )

    with pytest.raises(
        NormalizerContractError,
        match="NormalizationResult-compatible",
    ):
        identify_file(
            path,
            detector=FakeDetector(None),
            resolver=resolver,
            normalizer=IncompleteNormalizer(),
        )

    assert resolver.identify_calls == 1
    assert resolver.lookup_calls == 0


def test_identification_rejects_invalid_normalizer_representation(
    tmp_path: Path,
) -> None:
    import pytest

    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )

    path = tmp_path / "invalid.bin"
    path.write_bytes(b"physical-bytes")

    class InvalidRepresentationNormalizer:
        def identify(self, path: Path):
            class Result:
                content = NormalizedContentIdentity(
                    kind="disc",
                )
                local_metadata = None
                physical_representation = "rvz"

            return Result()

    with pytest.raises(
        NormalizerContractError,
        match=(
            "normalizer physical_representation must be RepresentationIdentity or None"
        ),
    ):
        identify_file(
            path,
            detector=FakeDetector(None),
            resolver=FakeResolver(
                physical=None,
                normalized=None,
            ),
            normalizer=InvalidRepresentationNormalizer(),
        )


def test_identification_without_normalizer_has_no_representation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "plain.bin"
    path.write_bytes(b"physical-bytes")

    result = identify_file(
        path,
        detector=FakeDetector(None),
        resolver=FakeResolver(
            physical=None,
            normalized=None,
        ),
    )

    assert result.physical_representation is None


def test_identification_result_exposes_common_state_helpers() -> None:
    result = IdentificationResult(
        physical_identity=RomIdentity(),
        platform_detection=PlatformDetection(),
    )

    assert not result.identified
    assert not result.has_normalized_content
    assert not result.has_physical_representation
    assert not result.has_local_metadata
    assert not result.has_release_conflict
    assert not result.has_platform_conflict


def test_identification_result_positive_state_helpers() -> None:
    canonical = CanonicalReleaseIdentity(
        release_name="Example",
        platform="nes",
        source="test",
        source_id="1",
    )

    result = IdentificationResult(
        physical_identity=RomIdentity(),
        platform_detection=PlatformDetection(),
        physical_match=canonical,
        normalized_content=NormalizedContentIdentity(
            kind="rom",
            hashes=HashSet(),
        ),
    )

    assert result.identified
    assert result.has_normalized_content
    assert not result.matched_via_normalization
    assert result.physical_representation_matched
    assert not result.normalized_content_matched


def test_identification_result_conflict_helpers() -> None:
    from rom_metadata_framework.reconciliation import (
        PlatformReconciliation,
        PlatformReconciliationStatus,
    )
    from rom_metadata_framework.release_reconciliation import (
        ReleaseReconciliation,
        ReleaseReconciliationStatus,
    )

    result = IdentificationResult(
        physical_identity=RomIdentity(),
        platform_detection=PlatformDetection(),
        release_reconciliation=ReleaseReconciliation(
            status=ReleaseReconciliationStatus.RELEASE_CONFLICT,
        ),
        platform_reconciliation=PlatformReconciliation(
            status=PlatformReconciliationStatus.CONFLICT,
        ),
    )

    assert not result.identified
    assert result.has_release_conflict
    assert result.has_platform_conflict



def test_identification_preserves_structural_inspection_without_normalization(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.inspection import (
        StructuralInspectionResult,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
    )
    from rom_metadata_framework.representation import (
        RepresentationIdentity,
    )

    path = tmp_path / "physical.iso"
    path.write_bytes(b"physical-bytes")

    representation = RepresentationIdentity(
        kind="disc-image",
        format="iso9660",
    )
    metadata = LocalContentMetadata(
        platform="ps2",
        boot={"path": r"cdrom0:\BOOT.ELF;1"},
    )

    class Inspector:
        name = "test"

        def inspect(self, inspected_path: Path):
            return StructuralInspectionResult(
                physical_representation=representation,
                local_metadata=metadata,
            )

    resolver = FakeResolver(
        physical=None,
        normalized=None,
    )

    result = identify_file(
        path,
        detector=FakeDetector("ps2"),
        resolver=resolver,
        inspector=Inspector(),
    )

    assert result.physical_representation is representation
    assert result.local_metadata is metadata
    assert result.normalized_content is None
    assert result.normalized_match is None

    # Structural inspection must not trigger normalized lookup.
    assert resolver.lookup_calls == 0


def test_identification_runs_physical_lookup_before_inspection(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.inspection import (
        StructuralInspectionResult,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
    )

    path = tmp_path / "physical.iso"
    path.write_bytes(b"physical-bytes")

    class OrderedResolver:
        def __init__(self) -> None:
            self.identify_calls = 0
            self.lookup_calls = 0

        def identify(self, identity):
            self.identify_calls += 1

        def identify_lookup(self, lookup):
            self.lookup_calls += 1

    resolver = OrderedResolver()

    class Inspector:
        name = "ordered"

        def inspect(self, inspected_path: Path):
            assert resolver.identify_calls == 1

            return StructuralInspectionResult(
                local_metadata=LocalContentMetadata(
                    platform="ps2",
                ),
            )

    result = identify_file(
        path,
        detector=FakeDetector("ps2"),
        resolver=resolver,
        inspector=Inspector(),
    )

    assert result.local_metadata is not None
    assert resolver.identify_calls == 1
    assert resolver.lookup_calls == 0


def test_identification_rejects_invalid_inspector_result(
    tmp_path: Path,
) -> None:
    import pytest

    from rom_metadata_framework.contracts import (
        InspectionContractError,
    )

    path = tmp_path / "physical.iso"
    path.write_bytes(b"physical-bytes")

    class InvalidInspector:
        name = "invalid"

        def inspect(self, inspected_path: Path):
            return "invalid"

    with pytest.raises(
        InspectionContractError,
        match="StructuralInspectionResult",
    ):
        identify_file(
            path,
            detector=FakeDetector("ps2"),
            resolver=FakeResolver(
                physical=None,
                normalized=None,
            ),
            inspector=InvalidInspector(),
        )


def test_identification_rejects_conflicting_structural_evidence(
    tmp_path: Path,
) -> None:
    import pytest

    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.contracts import (
        StructuralEvidenceConflictError,
    )
    from rom_metadata_framework.inspection import (
        StructuralInspectionResult,
    )
    from rom_metadata_framework.representation import (
        RepresentationIdentity,
    )

    path = tmp_path / "physical.iso"
    path.write_bytes(b"physical-bytes")

    class Inspector:
        name = "test"

        def inspect(self, inspected_path: Path):
            return StructuralInspectionResult(
                physical_representation=RepresentationIdentity(
                    kind="disc-image",
                    format="iso9660",
                ),
            )

    class NormalizationEvidence:
        content = NormalizedContentIdentity(
            kind="test-content",
            hashes=HashSet(
                sha1=(
                    "89abcdef0123456789abcdef"
                    "0123456789abcdef"
                )
            ),
        )
        local_metadata = None
        physical_representation = RepresentationIdentity(
            kind="disc-image",
            format="rvz",
        )

    class Normalizer:
        def identify(self, normalized_path: Path):
            return NormalizationEvidence()

    with pytest.raises(
        StructuralEvidenceConflictError,
        match="physical_representation",
    ):
        identify_file(
            path,
            detector=FakeDetector("ps2"),
            resolver=FakeResolver(
                physical=None,
                normalized=None,
            ),
            normalizer=Normalizer(),
            inspector=Inspector(),
        )
