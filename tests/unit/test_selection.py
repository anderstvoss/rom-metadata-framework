import pytest

from rom_metadata_framework.selection import (
    IdentificationSelection,
    RequestedIdentity,
)


def test_requested_identity_parses_platform_and_identifier() -> None:
    identity = RequestedIdentity.parse(
        "wii:RMCE01"
    )

    assert identity.platform == "wii"
    assert identity.identifier == "RMCE01"


def test_requested_identity_allows_colons_inside_identifier() -> None:
    identity = RequestedIdentity.parse(
        "switch:0100000000000000:extra"
    )

    assert identity.platform == "switch"
    assert (
        identity.identifier
        == "0100000000000000:extra"
    )


def test_requested_identity_requires_separator() -> None:
    with pytest.raises(
        ValueError,
        match="PLATFORM:IDENTIFIER",
    ):
        RequestedIdentity.parse("RMCE01")


def test_identity_implies_platform() -> None:
    selection = IdentificationSelection(
        identity=RequestedIdentity.parse(
            "wii:RMCE01"
        )
    )

    assert selection.platform == "wii"


def test_platform_and_identity_must_agree() -> None:
    with pytest.raises(
        ValueError,
        match="disagree",
    ):
        IdentificationSelection(
            platform="ps3",
            identity=RequestedIdentity.parse(
                "wii:RMCE01"
            ),
        )


def test_restrict_requires_selector() -> None:
    with pytest.raises(
        ValueError,
        match="restrict requires",
    ):
        IdentificationSelection(
            restrict=True,
        )


def test_restrict_identity_is_valid() -> None:
    selection = IdentificationSelection(
        identity=RequestedIdentity.parse(
            "wii:RMCE01"
        ),
        restrict=True,
    )

    assert selection.restrict
    assert selection.effective_platform == "wii"


def test_component_ownership_supports_shared_dolphin_platforms() -> None:
    from rom_metadata_framework.selection import (
        component_supports_platform,
    )

    assert component_supports_platform(
        "dolphin",
        "gc",
    )
    assert component_supports_platform(
        "dolphin",
        "wii",
    )
    assert not component_supports_platform(
        "dolphin",
        "ps3",
    )


def test_component_ownership_defaults_to_matching_slug() -> None:
    from rom_metadata_framework.selection import (
        component_supports_platform,
    )

    assert component_supports_platform(
        "ps3",
        "ps3",
    )
    assert not component_supports_platform(
        "ps3",
        "wii",
    )


def test_primary_identity_namespace_mapping() -> None:
    from rom_metadata_framework.selection import (
        primary_identity_namespace,
    )

    assert (
        primary_identity_namespace("wii")
        == "nintendo-game-id"
    )
    assert (
        primary_identity_namespace("ps3")
        == "ps3-title-id"
    )
    assert (
        primary_identity_namespace("xbox360")
        == "xbox360-title-id"
    )


def test_native_identifier_comparison_is_case_insensitive() -> None:
    from rom_metadata_framework.selection import (
        identifiers_equal,
    )

    assert identifiers_equal(
        "RMCE01",
        "rmce01",
    )

    assert not identifiers_equal(
        "RMCE01",
        "RSBE01",
    )
