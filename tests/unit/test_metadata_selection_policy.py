from rom_metadata_framework.canonical import CanonicalReleaseIdentity
from rom_metadata_framework.detection import PlatformDetection
from rom_metadata_framework.identification import IdentificationResult
from rom_metadata_framework.identity import RomIdentity
from rom_metadata_framework.local_metadata import (
    LocalContentMetadata,
    LocalMetadataProvenance,
    LocalMetadataValue,
)
from rom_metadata_framework.metadata import (
    MetadataProvenance,
    MetadataValue,
    ReleaseMetadata,
)
from rom_metadata_framework.metadata_provider import MetadataProviderResult
from rom_metadata_framework.metadata_reconciliation import reconcile_metadata


def provider_result(
    provider: str,
    title: str,
    *,
    authoritative: bool,
) -> MetadataProviderResult:
    return MetadataProviderResult(
        provider=provider,
        provider_id=f"{provider}-record",
        metadata=ReleaseMetadata(
            titles=(
                MetadataValue(
                    value=title,
                    provenance=MetadataProvenance(
                        source=provider,
                        source_id=f"{provider}-title",
                        authoritative=authoritative,
                    ),
                ),
            ),
        ),
    )


def test_provider_order_does_not_change_reconciliation() -> None:
    local = LocalContentMetadata(
        titles=(
            LocalMetadataValue(
                value="Example Game",
                provenance=LocalMetadataProvenance(
                    source="local",
                    method="header",
                ),
            ),
        ),
    )

    a = provider_result(
        "provider-a",
        "Example Game",
        authoritative=False,
    )
    b = provider_result(
        "provider-b",
        "Alternate Title",
        authoritative=True,
    )

    forward = reconcile_metadata(local, (a, b)).get("titles")
    reverse = reconcile_metadata(local, (b, a)).get("titles")

    assert forward == reverse
    assert forward.provider_values == (
        "alternate title",
        "example game",
    )


def test_authoritative_metadata_does_not_suppress_other_values() -> None:
    authoritative = provider_result(
        "provider-a",
        "Authoritative Title",
        authoritative=True,
    )
    ordinary = provider_result(
        "provider-b",
        "Ordinary Title",
        authoritative=False,
    )

    result = reconcile_metadata(
        None,
        (authoritative, ordinary),
    ).get("titles")

    assert result.provider_values == (
        "authoritative title",
        "ordinary title",
    )


def test_metadata_reconciliation_cannot_change_canonical_identity() -> None:
    canonical = CanonicalReleaseIdentity(
        release_name="Canonical Release",
        platform="nes",
        source="catalogue",
        source_id="release-1",
    )

    identification = IdentificationResult(
        physical_identity=RomIdentity(),
        platform_detection=PlatformDetection(),
        physical_match=canonical,
    )

    original = identification.canonical_match

    report = reconcile_metadata(
        LocalContentMetadata(
            titles=(
                LocalMetadataValue(
                    value="Local Conflicting Title",
                    provenance=LocalMetadataProvenance(
                        source="local",
                        method="header",
                    ),
                ),
            ),
        ),
        (
            provider_result(
                "provider-a",
                "Provider Conflicting Title",
                authoritative=True,
            ),
        ),
    )

    assert report.has_divergence
    assert identification.canonical_match is original
    assert identification.canonical_match is canonical
