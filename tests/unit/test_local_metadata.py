from datetime import UTC, datetime

import pytest

from rom_metadata_framework.local_metadata import (
    LocalContentMetadata,
    LocalIdentifier,
    LocalMetadataProvenance,
    LocalMetadataValue,
    LocalPlayerCount,
    LocalTimestamp,
)


def provenance(
    *,
    raw_value: str | None = None,
) -> LocalMetadataProvenance:
    return LocalMetadataProvenance(
        source="  Xbox-XBE  ",
        method="  Certificate-Field  ",
        raw_value=raw_value,
        details={" offset ": " 0x08 "},
    )


def test_local_provenance_normalizes_source_and_method() -> None:
    item = provenance(raw_value="  0x00000001  ")

    assert item.source == "xbox-xbe"
    assert item.method == "certificate-field"
    assert item.raw_value == "0x00000001"
    assert item.details == {"offset": "0x08"}

    with pytest.raises(TypeError):
        item.details["offset"] = "0x0c"


def test_local_identifier_normalizes_namespace() -> None:
    item = LocalIdentifier(
        namespace=" Xbox-Title-ID ",
        value=" 4D530004 ",
        provenance=provenance(),
    )

    assert item.namespace == "xbox-title-id"
    assert item.value == "4D530004"


def test_local_metadata_supports_shared_identity_fields() -> None:
    source = provenance()

    metadata = LocalContentMetadata(
        platform="original-xbox",
        titles=(
            LocalMetadataValue(
                value="Halo",
                provenance=source,
            ),
        ),
        identifiers=(
            LocalIdentifier(
                namespace="xbox-title-id",
                value="4D530004",
                provenance=source,
            ),
        ),
        executable_versions=(
            LocalMetadataValue(
                value="9",
                provenance=source,
            ),
        ),
        disc_numbers=(
            LocalMetadataValue(
                value=0,
                provenance=source,
            ),
        ),
        regions=(
            LocalMetadataValue(
                value="north-america",
                provenance=source,
            ),
        ),
    )

    assert metadata.platform == "xbox"
    assert metadata.titles[0].value == "Halo"
    assert metadata.identifiers[0].value == "4D530004"
    assert metadata.executable_versions[0].value == "9"
    assert metadata.disc_numbers[0].value == 0
    assert metadata.regions[0].value == "north-america"
    assert not metadata.empty


def test_local_metadata_retains_platform_specific_maps() -> None:
    metadata = LocalContentMetadata(
        platform="nes",
        hardware={
            "mapper": "4",
            "submapper": "2",
            "battery": "true",
        },
        media={
            "representation": "nes2",
        },
        native_metadata={
            "flags6": "42",
        },
    )

    assert metadata.hardware["mapper"] == "4"
    assert metadata.media["representation"] == "nes2"

    with pytest.raises(TypeError):
        metadata.hardware["mapper"] = "1"


def test_local_timestamp_preserves_kind_and_datetime() -> None:
    value = datetime(
        2003,
        11,
        14,
        20,
        55,
        30,
        tzinfo=UTC,
    )

    item = LocalTimestamp(
        kind=" Certificate ",
        value=value,
        provenance=provenance(),
    )

    assert item.kind == "certificate"
    assert item.value == value


def test_local_player_count_validates_range() -> None:
    item = LocalPlayerCount(
        minimum=1,
        maximum=4,
        context=" local ",
        provenance=provenance(),
    )

    assert item.context == "local"

    with pytest.raises(ValueError):
        LocalPlayerCount(
            minimum=2,
            maximum=1,
            provenance=provenance(),
        )


def test_empty_local_metadata_is_empty() -> None:
    assert LocalContentMetadata().empty


def test_platform_only_metadata_is_not_empty() -> None:
    assert not LocalContentMetadata(
        platform="gamecube",
    ).empty


@pytest.mark.parametrize(
    ("factory", "message"),
    (
        (
            lambda: LocalMetadataProvenance(
                source=" ",
                method="field",
            ),
            "source",
        ),
        (
            lambda: LocalMetadataProvenance(
                source="xbe",
                method=" ",
            ),
            "method",
        ),
        (
            lambda: LocalIdentifier(
                namespace=" ",
                value="value",
                provenance=provenance(),
            ),
            "namespace",
        ),
        (
            lambda: LocalIdentifier(
                namespace="xbox",
                value=" ",
                provenance=provenance(),
            ),
            "value",
        ),
    ),
)
def test_local_metadata_rejects_empty_required_strings(
    factory,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        factory()
