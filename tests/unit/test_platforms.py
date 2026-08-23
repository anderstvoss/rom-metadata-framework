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
        ("gba", "game-boy-advance"),
        ("game_boy_advance", "game-boy-advance"),
        ("gbc", "game-boy-color"),
        ("ps1", "playstation"),
        ("ps2", "playstation-2"),
        ("ps3", "playstation-3"),
        ("sony-playstation-3", "playstation-3"),
        ("original-xbox", "xbox"),
        ("nds", "nintendo-ds"),
        ("nintendo_ds", "nintendo-ds"),
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
        ("game-boy", 4),
        ("game-boy-advance", 5),
        ("game-boy-color", 6),
        ("nes", 7),
        ("playstation", 12),
        ("gamecube", 16),
        ("nintendo-ds", 18),
        ("wii", 19),
        ("playstation-2", 21),
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
        canonical_platform_name("xbox-360")
        == "xbox-360"
    )
    assert (
        canonical_platform_name("xbox360")
        == "xbox-360"
    )
    assert (
        canonical_platform_name(
            "xbox-360-console"
        )
        == "xbox-360"
    )
