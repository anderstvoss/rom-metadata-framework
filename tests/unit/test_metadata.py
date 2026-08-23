from datetime import date

import pytest

from rom_metadata_framework.metadata import (
    ExternalIdentifier,
    MetadataProvenance,
    MetadataValue,
    ReleaseDate,
    ReleaseMetadata,
)


def provenance(
    source: str = "provider-a",
    source_id: str = "record-1",
) -> MetadataProvenance:
    return MetadataProvenance(
        source=source,
        source_id=source_id,
    )


def test_metadata_provenance_normalizes_source() -> None:
    item = MetadataProvenance(
        source="  Provider-A  ",
        source_id="  record-1  ",
        details={" field ": " title "},
    )

    assert item.source == "provider-a"
    assert item.source_id == "record-1"
    assert item.details == {"field": "title"}


def test_metadata_provenance_details_are_immutable() -> None:
    item = MetadataProvenance(
        source="provider-a",
        source_id="record-1",
        details={"field": "title"},
    )

    with pytest.raises(TypeError):
        item.details["other"] = "value"


def test_metadata_provenance_requires_source() -> None:
    with pytest.raises(ValueError):
        MetadataProvenance(
            source="  ",
            source_id="record-1",
        )


def test_metadata_provenance_requires_source_id() -> None:
    with pytest.raises(ValueError):
        MetadataProvenance(
            source="provider-a",
            source_id="  ",
        )


def test_metadata_value_retains_exact_provider_value() -> None:
    value = MetadataValue(
        value="  The Legend of Zelda  ",
        provenance=provenance(),
    )

    assert value.value == "  The Legend of Zelda  "
    assert value.provenance.source == "provider-a"


def test_release_date_preserves_provenance_and_region() -> None:
    item = ReleaseDate(
        value=date(1987, 8, 22),
        region="  USA  ",
        provenance=provenance(),
    )

    assert item.value == date(1987, 8, 22)
    assert item.region == "USA"
    assert item.provenance.source_id == "record-1"


def test_release_date_allows_unspecified_region() -> None:
    item = ReleaseDate(
        value=date(1986, 2, 21),
        provenance=provenance(),
    )

    assert item.region is None


def test_external_identifier_normalizes_namespace() -> None:
    item = ExternalIdentifier(
        namespace="  IGDB  ",
        value="  1234  ",
        provenance=provenance(),
    )

    assert item.namespace == "igdb"
    assert item.value == "1234"


def test_external_identifier_requires_namespace() -> None:
    with pytest.raises(ValueError):
        ExternalIdentifier(
            namespace="  ",
            value="1234",
            provenance=provenance(),
        )


def test_external_identifier_requires_value() -> None:
    with pytest.raises(ValueError):
        ExternalIdentifier(
            namespace="igdb",
            value="  ",
            provenance=provenance(),
        )


def test_release_metadata_defaults_to_empty_evidence() -> None:
    metadata = ReleaseMetadata()

    assert metadata.titles == ()
    assert metadata.descriptions == ()
    assert metadata.developers == ()
    assert metadata.publishers == ()
    assert metadata.genres == ()
    assert metadata.release_dates == ()
    assert metadata.regions == ()
    assert metadata.languages == ()
    assert metadata.player_counts == ()
    assert metadata.multiplayer_features == ()
    assert metadata.age_ratings == ()
    assert metadata.media == ()
    assert metadata.external_ids == ()


def test_release_metadata_preserves_multiple_provider_values() -> None:
    provider_a = provenance("provider-a", "a-1")
    provider_b = provenance("provider-b", "b-9")

    metadata = ReleaseMetadata(
        titles=(
            MetadataValue(
                value="The Legend of Zelda",
                provenance=provider_a,
            ),
            MetadataValue(
                value="The Legend of Zelda",
                provenance=provider_b,
            ),
        ),
        developers=(
            MetadataValue(
                value="Nintendo R&D4",
                provenance=provider_a,
            ),
            MetadataValue(
                value="Nintendo EAD",
                provenance=provider_b,
            ),
        ),
    )

    assert len(metadata.titles) == 2
    assert len(metadata.developers) == 2
    assert metadata.developers[0].value == "Nintendo R&D4"
    assert metadata.developers[1].value == "Nintendo EAD"
    assert metadata.developers[0].provenance.source == "provider-a"
    assert metadata.developers[1].provenance.source == "provider-b"


def test_release_metadata_preserves_multiple_regional_dates() -> None:
    metadata = ReleaseMetadata(
        release_dates=(
            ReleaseDate(
                value=date(1986, 2, 21),
                region="Japan",
                provenance=provenance("provider-a", "jp"),
            ),
            ReleaseDate(
                value=date(1987, 8, 22),
                region="USA",
                provenance=provenance("provider-a", "us"),
            ),
        ),
    )

    assert len(metadata.release_dates) == 2
    assert metadata.release_dates[0].region == "Japan"
    assert metadata.release_dates[1].region == "USA"


def test_player_count_preserves_range_and_context() -> None:
    from rom_metadata_framework.metadata import PlayerCount

    item = PlayerCount(
        minimum=1,
        maximum=4,
        context="  local multiplayer  ",
        provenance=provenance(),
    )

    assert item.minimum == 1
    assert item.maximum == 4
    assert item.context == "local multiplayer"


def test_player_count_rejects_zero_minimum() -> None:
    from rom_metadata_framework.metadata import PlayerCount

    with pytest.raises(ValueError):
        PlayerCount(
            minimum=0,
            maximum=4,
            provenance=provenance(),
        )


def test_player_count_rejects_reversed_range() -> None:
    from rom_metadata_framework.metadata import PlayerCount

    with pytest.raises(ValueError):
        PlayerCount(
            minimum=4,
            maximum=2,
            provenance=provenance(),
        )


def test_age_rating_preserves_provider_rating() -> None:
    from rom_metadata_framework.metadata import AgeRating

    item = AgeRating(
        system="  ESRB  ",
        rating="  E10+  ",
        region="  USA  ",
        provenance=provenance(),
    )

    assert item.system == "esrb"
    assert item.rating == "E10+"
    assert item.region == "USA"


def test_age_rating_requires_system() -> None:
    from rom_metadata_framework.metadata import AgeRating

    with pytest.raises(ValueError):
        AgeRating(
            system="  ",
            rating="E",
            provenance=provenance(),
        )


def test_media_reference_preserves_provider_uri() -> None:
    from rom_metadata_framework.metadata import MediaReference

    item = MediaReference(
        kind="  Box-Art  ",
        uri="  https://example.invalid/image.png  ",
        width=600,
        height=900,
        provenance=provenance(),
    )

    assert item.kind == "box-art"
    assert item.uri == "https://example.invalid/image.png"
    assert item.width == 600
    assert item.height == 900


def test_media_reference_requires_uri() -> None:
    from rom_metadata_framework.metadata import MediaReference

    with pytest.raises(ValueError):
        MediaReference(
            kind="cover",
            uri="  ",
            provenance=provenance(),
        )


def test_media_reference_rejects_invalid_dimensions() -> None:
    from rom_metadata_framework.metadata import MediaReference

    with pytest.raises(ValueError):
        MediaReference(
            kind="cover",
            uri="https://example.invalid/cover.png",
            width=0,
            provenance=provenance(),
        )


def test_release_metadata_preserves_gameplay_rating_and_media_evidence() -> None:
    from rom_metadata_framework.metadata import (
        AgeRating,
        MediaReference,
        PlayerCount,
    )

    source = provenance("provider-a", "game-1")

    metadata = ReleaseMetadata(
        player_counts=(
            PlayerCount(
                minimum=1,
                maximum=4,
                context="local",
                provenance=source,
            ),
        ),
        multiplayer_features=(
            MetadataValue(
                value="split-screen",
                provenance=source,
            ),
            MetadataValue(
                value="co-op",
                provenance=source,
            ),
        ),
        age_ratings=(
            AgeRating(
                system="esrb",
                rating="E",
                region="USA",
                provenance=source,
            ),
        ),
        media=(
            MediaReference(
                kind="cover",
                uri="https://example.invalid/cover.png",
                provenance=source,
            ),
        ),
    )

    assert metadata.player_counts[0].maximum == 4
    assert len(metadata.multiplayer_features) == 2
    assert metadata.age_ratings[0].rating == "E"
    assert metadata.media[0].kind == "cover"


def test_release_metadata_keeps_duplicate_media_evidence() -> None:
    from rom_metadata_framework.metadata import MediaReference

    a = provenance("provider-a", "a")
    b = provenance("provider-b", "b")

    metadata = ReleaseMetadata(
        media=(
            MediaReference(
                kind="cover",
                uri="https://example.invalid/same.png",
                provenance=a,
            ),
            MediaReference(
                kind="cover",
                uri="https://example.invalid/same.png",
                provenance=b,
            ),
        ),
    )

    assert len(metadata.media) == 2
    assert metadata.media[0].provenance.source == "provider-a"
    assert metadata.media[1].provenance.source == "provider-b"
