from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


class UnknownPlatformError(ValueError):
    """Raised when a platform name or alias is not recognized."""


class UnsupportedPlatformBackendError(ValueError):
    """Raised when a platform has no mapping for a requested backend."""


@dataclass(frozen=True)
class PlatformDefinition:
    """Backend-independent canonical platform definition."""

    name: str
    display_name: str
    manufacturer: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackendPlatformMapping:
    """Backend-specific identifier for a canonical platform."""

    backend: str
    platform: str
    identifier: str | int


PLATFORMS: tuple[PlatformDefinition, ...] = (
    PlatformDefinition(
        name="snes",
        display_name="Super Nintendo Entertainment System",
        manufacturer="Nintendo",
        aliases=(
            "super-nintendo",
            "super-nintendo-entertainment-system",
        ),
    ),
    PlatformDefinition(
        name="genesis",
        display_name="Sega Genesis / Mega Drive",
        manufacturer="Sega",
        aliases=(
            "mega-drive",
            "sega-genesis",
        ),
    ),
    PlatformDefinition(
        name="n64",
        display_name="Nintendo 64",
        manufacturer="Nintendo",
        aliases=("nintendo-64",),
    ),
    PlatformDefinition(
        name="gb",
        display_name="Game Boy",
        manufacturer="Nintendo",
        aliases=(
            "game-boy",
            "gameboy",
        ),
    ),
    PlatformDefinition(
        name="gba",
        display_name="Game Boy Advance",
        manufacturer="Nintendo",
        aliases=(
            "game-boy-advance",
            "gameboy-advance",
        ),
    ),
    PlatformDefinition(
        name="gbc",
        display_name="Game Boy Color",
        manufacturer="Nintendo",
        aliases=(
            "game-boy-color",
            "gameboy-color",
        ),
    ),
    PlatformDefinition(
        name="nes",
        display_name="Nintendo Entertainment System",
        manufacturer="Nintendo",
        aliases=("nintendo-entertainment-system",),
    ),
    PlatformDefinition(
        name="psx",
        display_name="PlayStation",
        manufacturer="Sony",
        aliases=(
            "playstation",
            "ps1",
            "sony-playstation",
        ),
    ),
    PlatformDefinition(
        name="gc",
        display_name="Nintendo GameCube",
        manufacturer="Nintendo",
        aliases=(
            "gamecube",
            "game-cube",
            "nintendo-gamecube",
            "gcn",
            "ngc",
        ),
    ),
    PlatformDefinition(
        name="nds",
        display_name="Nintendo DS",
        manufacturer="Nintendo",
        aliases=(
            "nintendo-ds",
            "ds",
        ),
    ),
    PlatformDefinition(
        name="wii",
        display_name="Wii",
        manufacturer="Nintendo",
        aliases=("nintendo-wii",),
    ),
    PlatformDefinition(
        name="ps2",
        display_name="PlayStation 2",
        manufacturer="Sony",
        aliases=(
            "playstation-2",
            "sony-playstation-2",
        ),
    ),
    PlatformDefinition(
        name="ps3",
        display_name="PlayStation 3",
        manufacturer="Sony",
        aliases=(
            "playstation-3",
            "sony-playstation-3",
        ),
    ),
    PlatformDefinition(
        name="xbox",
        display_name="Xbox",
        manufacturer="Microsoft",
        aliases=(
            "original-xbox",
            "xbox-original",
        ),
    ),
    PlatformDefinition(
        name="xbox360",
        display_name="Xbox 360",
        manufacturer="Microsoft",
        aliases=(
            "xbox-360",
            "xbox-360-console",
        ),
    ),
    PlatformDefinition(
        name="switch",
        display_name="Nintendo Switch",
        manufacturer="Nintendo",
        aliases=(
            "nintendo-switch",
            "nintendo-switch-console",
        ),
    ),
    PlatformDefinition(
        name="psp",
        display_name="PlayStation Portable",
        manufacturer="Sony",
        aliases=(
            "playstation-portable",
            "sony-psp",
        ),
    ),
)


BACKEND_PLATFORM_MAPPINGS: tuple[BackendPlatformMapping, ...] = (
    BackendPlatformMapping("rcheevos", "genesis", 1),
    BackendPlatformMapping("rcheevos", "n64", 2),
    BackendPlatformMapping("rcheevos", "snes", 3),
    BackendPlatformMapping("rcheevos", "gb", 4),
    BackendPlatformMapping("rcheevos", "gba", 5),
    BackendPlatformMapping("rcheevos", "gbc", 6),
    BackendPlatformMapping("rcheevos", "nes", 7),
    BackendPlatformMapping("rcheevos", "psx", 12),
    BackendPlatformMapping("rcheevos", "gc", 16),
    BackendPlatformMapping("rcheevos", "nds", 18),
    BackendPlatformMapping("rcheevos", "wii", 19),
    BackendPlatformMapping("rcheevos", "ps2", 21),
    BackendPlatformMapping("rcheevos", "xbox", 22),
    BackendPlatformMapping("rcheevos", "psp", 41),
)


def _normalize_key(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)

    if not normalized:
        raise ValueError("identifier must not be empty")

    return normalized


def _build_platform_index() -> Mapping[str, PlatformDefinition]:
    index: dict[str, PlatformDefinition] = {}

    canonical_names: set[str] = set()

    for platform in PLATFORMS:
        canonical = _normalize_key(platform.name)

        if canonical != platform.name:
            raise RuntimeError(
                f"platform canonical name is not normalized: {platform.name!r}"
            )

        if canonical in canonical_names:
            raise RuntimeError(f"duplicate canonical platform: {canonical!r}")

        canonical_names.add(canonical)

        for key in (platform.name, *platform.aliases):
            normalized = _normalize_key(key)

            existing = index.get(normalized)

            if existing is not None:
                raise RuntimeError(
                    f"duplicate platform alias {normalized!r}: "
                    f"{existing.name!r} and {platform.name!r}"
                )

            index[normalized] = platform

    return MappingProxyType(index)


_PLATFORM_INDEX = _build_platform_index()


def _build_backend_mapping_index() -> Mapping[
    tuple[str, str],
    BackendPlatformMapping,
]:
    index: dict[tuple[str, str], BackendPlatformMapping] = {}

    canonical_platforms = {platform.name for platform in PLATFORMS}

    for mapping in BACKEND_PLATFORM_MAPPINGS:
        backend = _normalize_key(mapping.backend)
        platform = _normalize_key(mapping.platform)

        if platform not in canonical_platforms:
            raise RuntimeError(
                f"backend mapping references unknown platform {platform!r}"
            )

        key = (backend, platform)

        if key in index:
            raise RuntimeError(f"duplicate backend platform mapping: {key!r}")

        index[key] = mapping

    return MappingProxyType(index)


_BACKEND_MAPPING_INDEX = _build_backend_mapping_index()


def resolve_platform(value: str) -> PlatformDefinition:
    """Resolve a canonical platform from a name or alias."""

    try:
        normalized = _normalize_key(value)
    except ValueError as exc:
        raise UnknownPlatformError("platform must not be empty") from exc

    try:
        return _PLATFORM_INDEX[normalized]
    except KeyError as exc:
        raise UnknownPlatformError(f"unknown platform: {value!r}") from exc


def canonical_platform_name(value: str) -> str:
    """Return the canonical framework platform name."""

    return resolve_platform(value).name


def platform_display_name(value: str) -> str:
    """Return the human-readable name for a platform."""

    return resolve_platform(value).display_name


def platform_manufacturer(value: str) -> str:
    """Return the manufacturer associated with a platform."""

    return resolve_platform(value).manufacturer


def backend_platform_mapping(
    backend: str,
    platform: str,
) -> BackendPlatformMapping:
    """Return backend-specific metadata for a platform."""

    canonical = canonical_platform_name(platform)

    try:
        normalized_backend = _normalize_key(backend)
    except ValueError as exc:
        raise UnsupportedPlatformBackendError("backend must not be empty") from exc

    try:
        return _BACKEND_MAPPING_INDEX[(normalized_backend, canonical)]
    except KeyError as exc:
        raise UnsupportedPlatformBackendError(
            f"platform {canonical!r} is not supported by backend {normalized_backend!r}"
        ) from exc


def backend_platform_identifier(
    backend: str,
    platform: str,
) -> str | int:
    """Return a backend-specific platform identifier."""

    return backend_platform_mapping(
        backend,
        platform,
    ).identifier


def rcheevos_console_id(platform: str) -> int:
    """Return the rcheevos console ID for a platform."""

    identifier = backend_platform_identifier(
        "rcheevos",
        platform,
    )

    if not isinstance(identifier, int):
        raise TypeError("rcheevos platform identifier must be an integer")

    return identifier
