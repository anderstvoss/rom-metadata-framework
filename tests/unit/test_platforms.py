import pytest

from rom_metadata_framework.platforms import (
    BACKEND_PLATFORM_MAPPINGS,
    PLATFORMS,
    UnknownPlatformError,
    UnsupportedPlatformBackendError,
    backend_platform_identifier,
    canonical_platform_name,
    rcheevos_console_id,
    resolve_platform,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("snes", "snes"),
        ("SNES", "snes"),
        (" super-nintendo ", "snes"),
        ("super_nintendo", "snes"),
        ("super nintendo", "snes"),
        ("SUPER__NINTENDO", "snes"),
        ("super---nintendo", "snes"),
        ("genesis", "genesis"),
        ("mega-drive", "genesis"),
        ("mega_drive", "genesis"),
        ("nintendo 64", "n64"),
        ("gba", "gba"),
        ("game_boy_advance", "gba"),
        ("gbc", "gbc"),
        ("ps1", "psx"),
        ("ps2", "ps2"),
        ("ps3", "ps3"),
        ("sony-playstation-3", "ps3"),
        ("original-xbox", "xbox"),
        ("nds", "nds"),
        ("nintendo_ds", "nds"),
    ],
)
def test_platform_aliases_resolve_to_canonical_name(
    value: str,
    expected: str,
) -> None:
    assert canonical_platform_name(value) == expected


@pytest.mark.parametrize(
    ("platform", "console_id"),
    [
        ("genesis", 1),
        ("n64", 2),
        ("snes", 3),
        ("gb", 4),
        ("gba", 5),
        ("gbc", 6),
        ("nes", 7),
        ("psx", 12),
        ("gc", 16),
        ("nds", 18),
        ("wii", 19),
        ("ps2", 21),
        ("xbox", 22),
        ("psp", 41),
    ],
)
def test_rcheevos_console_ids(
    platform: str,
    console_id: int,
) -> None:
    assert rcheevos_console_id(platform) == console_id


def test_backend_platform_identifier_is_generic() -> None:
    assert (
        backend_platform_identifier(
            "rcheevos",
            "super-nintendo",
        )
        == 3
    )


def test_unknown_platform_is_rejected() -> None:
    with pytest.raises(UnknownPlatformError):
        resolve_platform("definitely-not-a-platform")


def test_empty_platform_is_rejected() -> None:
    with pytest.raises(UnknownPlatformError):
        resolve_platform("   ")


def test_unknown_backend_mapping_is_rejected() -> None:
    with pytest.raises(UnsupportedPlatformBackendError):
        backend_platform_identifier(
            "future-backend",
            "snes",
        )


def test_canonical_platform_names_are_unique() -> None:
    names = [platform.name for platform in PLATFORMS]

    assert len(names) == len(set(names))


def test_backend_platform_pairs_are_unique() -> None:
    pairs = [
        (mapping.backend, mapping.platform)
        for mapping in BACKEND_PLATFORM_MAPPINGS
    ]

    assert len(pairs) == len(set(pairs))


def test_rcheevos_console_ids_are_unique() -> None:
    identifiers = [
        mapping.identifier
        for mapping in BACKEND_PLATFORM_MAPPINGS
        if mapping.backend == "rcheevos"
    ]

    assert len(identifiers) == len(set(identifiers))


def test_xbox360_platform_aliases() -> None:
    assert (
        canonical_platform_name("xbox360")
        == "xbox360"
    )
    assert (
        canonical_platform_name("xbox360")
        == "xbox360"
    )
    assert (
        canonical_platform_name(
            "xbox-360-console"
        )
        == "xbox360"
    )


def test_nintendo_switch_platform_aliases() -> None:
    assert (
        canonical_platform_name(
            "switch"
        )
        == "switch"
    )
    assert (
        canonical_platform_name("switch")
        == "switch"
    )
    assert (
        canonical_platform_name(
            "nintendo-switch-console"
        )
        == "switch"
    )


def test_platform_definitions_have_presentation_metadata() -> None:
    for platform in PLATFORMS:
        assert platform.name
        assert platform.display_name
        assert platform.manufacturer


def test_platform_display_names_are_unique() -> None:
    names = [
        platform.display_name
        for platform in PLATFORMS
    ]

    assert len(names) == len(set(names))


def test_legacy_canonical_names_remain_aliases() -> None:
    expected = {
        "game-boy": "gb",
        "game-boy-advance": "gba",
        "game-boy-color": "gbc",
        "playstation": "psx",
        "gamecube": "gc",
        "nintendo-ds": "nds",
        "playstation-2": "ps2",
        "playstation-3": "ps3",
        "xbox-360": "xbox360",
        "nintendo-switch": "switch",
    }

    for legacy, canonical in expected.items():
        assert (
            canonical_platform_name(legacy)
            == canonical
        )


def test_community_platform_identifiers() -> None:
    expected = {
        "snes",
        "genesis",
        "n64",
        "gb",
        "gba",
        "gbc",
        "nes",
        "psx",
        "gc",
        "nds",
        "wii",
        "ps2",
        "ps3",
        "xbox",
        "xbox360",
        "switch",
        "psp",
    }

    assert {
        platform.name
        for platform in PLATFORMS
    } == expected
