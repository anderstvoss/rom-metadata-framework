from types import MappingProxyType

import pytest

from rom_metadata_framework.content import (
    NormalizedContentIdentity,
)
from rom_metadata_framework.identity import HashSet


def test_normalized_content_identity() -> None:
    identity = NormalizedContentIdentity(
        kind="disc",
        hashes=HashSet(
            sha1=(
                "d4e70c064cc714ba8400a849"
                "cf299dbd1aa326fc"
            ),
        ),
        specialized_identifiers={
            "RetroAchievements":
                "326d2c2de5c8957637780da332ab9dbb",
        },
        metadata={
            "game_id": "GALE01",
            "revision": "2",
        },
    )

    assert identity.kind == "disc"
    assert (
        identity.hashes.sha1
        == "d4e70c064cc714ba8400a849cf299dbd1aa326fc"
    )
    assert (
        identity.specialized_identifiers[
            "retroachievements"
        ]
        == "326d2c2de5c8957637780da332ab9dbb"
    )
    assert identity.metadata["game_id"] == "GALE01"

    assert isinstance(
        identity.specialized_identifiers,
        MappingProxyType,
    )
    assert isinstance(
        identity.metadata,
        MappingProxyType,
    )


def test_content_kind_is_normalized() -> None:
    identity = NormalizedContentIdentity(
        kind="  DISC  ",
    )

    assert identity.kind == "disc"


@pytest.mark.parametrize(
    "kind",
    [
        "",
        "   ",
    ],
)
def test_content_kind_must_not_be_empty(
    kind: str,
) -> None:
    with pytest.raises(ValueError):
        NormalizedContentIdentity(
            kind=kind,
        )


def test_content_identifier_namespace_is_normalized() -> None:
    identity = NormalizedContentIdentity(
        kind="cartridge",
        specialized_identifiers={
            " RetroAchievements ":
                "0123456789abcdef0123456789abcdef",
        },
    )

    assert (
        identity.specialized_identifiers[
            "retroachievements"
        ]
        == "0123456789abcdef0123456789abcdef"
    )


def test_content_metadata_is_immutable() -> None:
    identity = NormalizedContentIdentity(
        kind="disc",
        metadata={
            "game_id": "GALE01",
        },
    )

    with pytest.raises(TypeError):
        identity.metadata["game_id"] = "OTHER"
