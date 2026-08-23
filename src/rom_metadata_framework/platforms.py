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
        aliases=(
            "super-nintendo",
            "super-nintendo-entertainment-system",
        ),
    ),
    PlatformDefinition(
        name="genesis",
        aliases=(
            "mega-drive",
            "sega-genesis",
        ),
    ),
    PlatformDefinition(
        name="n64",
        aliases=("nintendo-64",),
    ),
    PlatformDefinition(
        name="game-boy",
        aliases=(
            "gameboy",
            "gb",
        ),
    ),
    PlatformDefinition(
        name="game-boy-advance",
        aliases=(
            "gameboy-advance",
            "gba",
        ),
    ),
    PlatformDefinition(
        name="game-boy-color",
        aliases=(
            "gameboy-color",
            "gbc",
        ),
    ),
    PlatformDefinition(
        name="nes",
        aliases=("nintendo-entertainment-system",),
    ),
    PlatformDefinition(
        name="playstation",
        aliases=(
            "ps1",
            "psx",
            "sony-playstation",
        ),
    ),
    PlatformDefinition(
        name="gamecube",
        aliases=(
            "game-cube",
            "nintendo-gamecube",
        ),
    ),
    PlatformDefinition(
        name="nintendo-ds",
        aliases=(
            "nds",
            "ds",
        ),
    ),
    PlatformDefinition(
        name="wii",
        aliases=("nintendo-wii",),
    ),
    PlatformDefinition(
        name="playstation-2",
        aliases=(
            "ps2",
            "sony-playstation-2",
        ),
    ),
    PlatformDefinition(
        name="playstation-3",
        aliases=(
            "ps3",
            "sony-playstation-3",
        ),
    ),
    PlatformDefinition(
        name="xbox",
        aliases=(
            "original-xbox",
            "xbox-original",
        ),
    ),
    PlatformDefinition(
        name="xbox-360",
        aliases=(
            "xbox360",
            "xbox-360-console",
        ),
    ),
    PlatformDefinition(
        name="psp",
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
    BackendPlatformMapping("rcheevos", "game-boy", 4),
    BackendPlatformMapping("rcheevos", "game-boy-advance", 5),
    BackendPlatformMapping("rcheevos", "game-boy-color", 6),
    BackendPlatformMapping("rcheevos", "nes", 7),
    BackendPlatformMapping("rcheevos", "playstation", 12),
    BackendPlatformMapping("rcheevos", "gamecube", 16),
    BackendPlatformMapping("rcheevos", "nintendo-ds", 18),
    BackendPlatformMapping("rcheevos", "wii", 19),
    BackendPlatformMapping("rcheevos", "playstation-2", 21),
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
