import pytest

from rom_metadata_framework.canonical import CanonicalReleaseIdentity
from rom_metadata_framework.metadata import (
    MetadataProvenance,
    MetadataValue,
    ReleaseMetadata,
)
from rom_metadata_framework.metadata_provider import (
    MetadataProvider,
    MetadataProviderResult,
)


def identity() -> CanonicalReleaseIdentity:
    return CanonicalReleaseIdentity(
        release_name="Example Game (USA)",
        platform="nes",
        source="catalogue-a",
        source_id="release-1",
        title="Example Game",
    )


def test_provider_result_normalizes_provider_identity() -> None:
    result = MetadataProviderResult(
        provider="  Provider-A  ",
        provider_id="  record-42  ",
        metadata=ReleaseMetadata(),
    )

    assert result.provider == "provider-a"
    assert result.provider_id == "record-42"


def test_provider_result_requires_provider() -> None:
    with pytest.raises(ValueError):
        MetadataProviderResult(
            provider="  ",
            provider_id="record-42",
            metadata=ReleaseMetadata(),
        )


def test_provider_result_requires_provider_id() -> None:
    with pytest.raises(ValueError):
        MetadataProviderResult(
            provider="provider-a",
            provider_id="  ",
            metadata=ReleaseMetadata(),
        )


def test_provider_result_allows_empty_normalized_metadata() -> None:
    result = MetadataProviderResult(
        provider="provider-a",
        provider_id="record-42",
        metadata=ReleaseMetadata(),
    )

    assert result.metadata == ReleaseMetadata()


def test_provider_result_preserves_field_level_provenance() -> None:
    provenance = MetadataProvenance(
        source="provider-a",
        source_id="field-record-9",
    )

    result = MetadataProviderResult(
        provider="provider-a",
        provider_id="record-42",
        metadata=ReleaseMetadata(
            titles=(
                MetadataValue(
                    value="Example Game",
                    provenance=provenance,
                ),
            ),
        ),
    )

    assert result.provider_id == "record-42"
    assert (
        result.metadata.titles[0].provenance.source_id
        == "field-record-9"
    )


def test_structural_metadata_provider_satisfies_protocol() -> None:
    class ExampleProvider:
        @property
        def name(self) -> str:
            return "example"

        def lookup_metadata(self, identity):
            return MetadataProviderResult(
                provider=self.name,
                provider_id=identity.source_id,
                metadata=ReleaseMetadata(),
            )

    provider = ExampleProvider()

    assert isinstance(provider, MetadataProvider)


def test_provider_contract_receives_canonical_release_identity() -> None:
    observed = {}

    class ExampleProvider:
        name = "example"

        def lookup_metadata(self, release):
            observed["identity"] = release

    release = identity()
    result = ExampleProvider().lookup_metadata(release)

    assert result is None
    assert observed["identity"] is release


def test_none_represents_no_provider_match() -> None:
    class MissingProvider:
        name = "missing"

        def lookup_metadata(self, identity):
            return None

    assert MissingProvider().lookup_metadata(identity()) is None


def test_match_with_no_supported_fields_is_distinct_from_no_match() -> None:
    class MatchingProvider:
        name = "matching"

        def lookup_metadata(self, identity):
            return MetadataProviderResult(
                provider=self.name,
                provider_id="matched-record",
                metadata=ReleaseMetadata(),
            )

    result = MatchingProvider().lookup_metadata(identity())

    assert result is not None
    assert result.provider_id == "matched-record"
    assert result.metadata == ReleaseMetadata()


def test_provider_result_normalizes_match_method() -> None:
    result = MetadataProviderResult(
        provider="provider-a",
        provider_id="record-42",
        metadata=ReleaseMetadata(),
        match_method="  External-ID  ",
    )

    assert result.match_method == "external-id"


def test_provider_result_allows_unspecified_match_method() -> None:
    result = MetadataProviderResult(
        provider="provider-a",
        provider_id="record-42",
        metadata=ReleaseMetadata(),
    )

    assert result.match_method is None


def test_provider_result_details_are_normalized_and_immutable() -> None:
    result = MetadataProviderResult(
        provider="provider-a",
        provider_id="record-42",
        metadata=ReleaseMetadata(),
        details={
            " query ": " Example Game ",
            " endpoint ": " releases ",
        },
    )

    assert result.details == {
        "query": "Example Game",
        "endpoint": "releases",
    }

    with pytest.raises(TypeError):
        result.details["other"] = "value"


def test_provider_result_rejects_empty_detail_key() -> None:
    with pytest.raises(ValueError):
        MetadataProviderResult(
            provider="provider-a",
            provider_id="record-42",
            metadata=ReleaseMetadata(),
            details={"  ": "value"},
        )


def test_match_diagnostics_do_not_change_metadata_provenance() -> None:
    field_provenance = MetadataProvenance(
        source="provider-a",
        source_id="field-record",
    )

    result = MetadataProviderResult(
        provider="provider-a",
        provider_id="matched-record",
        match_method="external-id",
        details={"external_id": "abc-123"},
        metadata=ReleaseMetadata(
            titles=(
                MetadataValue(
                    value="Example Game",
                    provenance=field_provenance,
                ),
            ),
        ),
    )

    assert result.provider_id == "matched-record"
    assert result.match_method == "external-id"
    assert result.details["external_id"] == "abc-123"
    assert (
        result.metadata.titles[0].provenance.source_id
        == "field-record"
    )
