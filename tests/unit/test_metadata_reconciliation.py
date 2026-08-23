from rom_metadata_framework.local_metadata import (
    LocalContentMetadata,
    LocalIdentifier,
    LocalMetadataProvenance,
    LocalMetadataValue,
    LocalPlayerCount,
)
from rom_metadata_framework.metadata import (
    ExternalIdentifier,
    MediaReference,
    MetadataProvenance,
    MetadataValue,
    PlayerCount,
    ReleaseMetadata,
)
from rom_metadata_framework.metadata_provider import (
    MetadataProviderResult,
)
from rom_metadata_framework.metadata_reconciliation import (
    COMPARABLE_METADATA_FIELDS,
    MetadataFieldReconciliationStatus,
    reconcile_metadata,
)


def local_provenance() -> LocalMetadataProvenance:
    return LocalMetadataProvenance(
        source="test-local",
        method="header",
    )


def provider_provenance(
    source: str = "provider-a",
) -> MetadataProvenance:
    return MetadataProvenance(
        source=source,
        source_id="record-1",
    )


def local_value(value: str) -> LocalMetadataValue[str]:
    return LocalMetadataValue(
        value=value,
        provenance=local_provenance(),
    )


def provider_value(
    value: str,
    *,
    source: str = "provider-a",
) -> MetadataValue[str]:
    return MetadataValue(
        value=value,
        provenance=provider_provenance(source),
    )


def provider_result(
    metadata: ReleaseMetadata,
    *,
    provider: str = "provider-a",
) -> MetadataProviderResult:
    return MetadataProviderResult(
        provider=provider,
        provider_id=f"{provider}-record",
        metadata=metadata,
    )


def test_exact_text_values_agree_after_safe_normalization() -> None:
    report = reconcile_metadata(
        LocalContentMetadata(
            titles=(local_value("  Example   Game "),),
        ),
        (
            provider_result(
                ReleaseMetadata(
                    titles=(provider_value("example game"),),
                )
            ),
        ),
    )

    result = report.get("titles")

    assert result.status is MetadataFieldReconciliationStatus.AGREEMENT
    assert result.local_values == ("example game",)
    assert result.provider_values == ("example game",)
    assert result.agreement_values == ("example game",)
    assert not result.has_divergence


def test_local_only_field_is_reported() -> None:
    report = reconcile_metadata(
        LocalContentMetadata(
            developers=(local_value("Local Developer"),),
        ),
        (),
    )

    result = report.get("developers")

    assert result.status is MetadataFieldReconciliationStatus.LOCAL_ONLY
    assert result.local_values == ("local developer",)
    assert result.provider_values == ()


def test_provider_only_field_is_reported() -> None:
    report = reconcile_metadata(
        None,
        (
            provider_result(
                ReleaseMetadata(
                    publishers=(provider_value("Provider Publisher"),),
                )
            ),
        ),
    )

    result = report.get("publishers")

    assert result.status is MetadataFieldReconciliationStatus.PROVIDER_ONLY
    assert result.local_values == ()
    assert result.provider_values == ("provider publisher",)


def test_partial_agreement_is_not_treated_as_conflict() -> None:
    report = reconcile_metadata(
        LocalContentMetadata(
            languages=(local_value("English"),),
        ),
        (
            provider_result(
                ReleaseMetadata(
                    languages=(
                        provider_value("English"),
                        provider_value("French"),
                    ),
                )
            ),
        ),
    )

    result = report.get("languages")

    assert result.status is MetadataFieldReconciliationStatus.PARTIAL_AGREEMENT
    assert result.agreement_values == ("english",)
    assert not result.has_divergence
    assert not report.has_divergence


def test_disjoint_values_are_divergent_but_not_selected() -> None:
    report = reconcile_metadata(
        LocalContentMetadata(
            regions=(local_value("Japan"),),
        ),
        (
            provider_result(
                ReleaseMetadata(
                    regions=(provider_value("USA"),),
                )
            ),
        ),
    )

    result = report.get("regions")

    assert result.status is MetadataFieldReconciliationStatus.DIVERGENT
    assert result.local_values == ("japan",)
    assert result.provider_values == ("usa",)
    assert result.agreement_values == ()
    assert result.has_divergence
    assert report.has_divergence


def test_provider_values_are_aggregated_without_provider_precedence() -> None:
    report = reconcile_metadata(
        LocalContentMetadata(
            titles=(local_value("Example Game"),),
        ),
        (
            provider_result(
                ReleaseMetadata(
                    titles=(provider_value("Example Game"),),
                ),
                provider="provider-a",
            ),
            provider_result(
                ReleaseMetadata(
                    titles=(
                        provider_value(
                            "Alternate Title",
                            source="provider-b",
                        ),
                    ),
                ),
                provider="provider-b",
            ),
        ),
    )

    result = report.get("titles")

    assert result.status is MetadataFieldReconciliationStatus.PARTIAL_AGREEMENT
    assert result.provider_values == (
        "alternate title",
        "example game",
    )
    assert result.agreement_values == ("example game",)


def test_player_counts_compare_range_and_context() -> None:
    local = LocalContentMetadata(
        player_counts=(
            LocalPlayerCount(
                minimum=1,
                maximum=4,
                context=" Local ",
                provenance=local_provenance(),
            ),
        ),
    )

    provider = provider_result(
        ReleaseMetadata(
            player_counts=(
                PlayerCount(
                    minimum=1,
                    maximum=4,
                    context="local",
                    provenance=provider_provenance(),
                ),
            ),
        )
    )

    result = reconcile_metadata(
        local,
        (provider,),
    ).get("player_counts")

    assert result.status is MetadataFieldReconciliationStatus.AGREEMENT
    assert result.agreement_values == ("1-4@local",)


def test_unrepresented_fields_are_unresolved() -> None:
    report = reconcile_metadata(
        LocalContentMetadata(),
        (),
    )

    for field_name in COMPARABLE_METADATA_FIELDS:
        result = report.get(field_name)

        assert result.status is MetadataFieldReconciliationStatus.UNRESOLVED


def test_structurally_different_media_fields_are_not_compared() -> None:
    local = LocalContentMetadata(
        media={
            "representation": "ines",
        },
    )

    provider = provider_result(
        ReleaseMetadata(
            media=(
                MediaReference(
                    kind="boxart",
                    uri="https://example.invalid/image.png",
                    provenance=provider_provenance(),
                ),
            ),
        )
    )

    report = reconcile_metadata(
        local,
        (provider,),
    )

    assert "media" not in COMPARABLE_METADATA_FIELDS

    try:
        report.get("media")
    except KeyError:
        pass
    else:
        raise AssertionError(
            "structurally different media fields must not be reconciled"
        )


def test_identifiers_compare_namespace_and_opaque_value() -> None:
    local = LocalContentMetadata(
        identifiers=(
            LocalIdentifier(
                namespace=" Xbox-Title-ID ",
                value="4D530004",
                provenance=local_provenance(),
            ),
        ),
    )

    provider = provider_result(
        ReleaseMetadata(
            external_ids=(
                ExternalIdentifier(
                    namespace="xbox-title-id",
                    value="4D530004",
                    provenance=provider_provenance(),
                ),
            ),
        )
    )

    result = reconcile_metadata(
        local,
        (provider,),
    ).get("identifiers")

    assert result.status is MetadataFieldReconciliationStatus.AGREEMENT
    assert result.local_values == ('["xbox-title-id","4D530004"]',)
    assert result.provider_values == ('["xbox-title-id","4D530004"]',)
    assert result.agreement_values == ('["xbox-title-id","4D530004"]',)


def test_identifier_namespace_is_part_of_semantic_identity() -> None:
    local = LocalContentMetadata(
        identifiers=(
            LocalIdentifier(
                namespace="xbox-title-id",
                value="4D530004",
                provenance=local_provenance(),
            ),
        ),
    )

    provider = provider_result(
        ReleaseMetadata(
            external_ids=(
                ExternalIdentifier(
                    namespace="provider-record-id",
                    value="4D530004",
                    provenance=provider_provenance(),
                ),
            ),
        )
    )

    result = reconcile_metadata(
        local,
        (provider,),
    ).get("identifiers")

    assert result.status is MetadataFieldReconciliationStatus.DIVERGENT
    assert result.agreement_values == ()


def test_identifier_values_remain_case_sensitive() -> None:
    local = LocalContentMetadata(
        identifiers=(
            LocalIdentifier(
                namespace="opaque-id",
                value="ABC123",
                provenance=local_provenance(),
            ),
        ),
    )

    provider = provider_result(
        ReleaseMetadata(
            external_ids=(
                ExternalIdentifier(
                    namespace="opaque-id",
                    value="abc123",
                    provenance=provider_provenance(),
                ),
            ),
        )
    )

    result = reconcile_metadata(
        local,
        (provider,),
    ).get("identifiers")

    assert result.status is MetadataFieldReconciliationStatus.DIVERGENT
    assert result.agreement_values == ()


def test_semantically_unmapped_fields_remain_outside_reconciliation() -> None:
    for field_name in (
        "timestamps",
        "release_dates",
        "ratings",
        "age_ratings",
        "media",
    ):
        assert field_name not in COMPARABLE_METADATA_FIELDS


def test_identifier_pair_encoding_cannot_collapse_delimiter_values() -> None:
    local = LocalContentMetadata(
        identifiers=(
            LocalIdentifier(
                namespace="a:b",
                value="c",
                provenance=local_provenance(),
            ),
        ),
    )

    provider = provider_result(
        ReleaseMetadata(
            external_ids=(
                ExternalIdentifier(
                    namespace="a",
                    value="b:c",
                    provenance=provider_provenance(),
                ),
            ),
        )
    )

    result = reconcile_metadata(
        local,
        (provider,),
    ).get("identifiers")

    assert result.status is MetadataFieldReconciliationStatus.DIVERGENT
    assert result.local_values == (
        '["a:b","c"]',
    )
    assert result.provider_values == (
        '["a","b:c"]',
    )
    assert result.agreement_values == ()
