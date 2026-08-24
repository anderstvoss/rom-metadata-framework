from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .detection import CompositePlatformDetector
from .dolphin import (
    DOLPHIN_EXECUTABLE,
    DolphinAdapter,
    DolphinPlatformDetector,
)
from .inspection import CompositeStructuralInspector
from .nes import NesAdapter, NesPlatformDetector
from .ps2 import (
    Ps2PlatformDetector,
    Ps2StructuralInspector,
)
from .ps3 import (
    Ps3PlatformDetector,
    Ps3StructuralInspector,
)
from .routing import CompositeNormalizer
from .switch import (
    NintendoSwitchPlatformDetector,
    NintendoSwitchStructuralInspector,
)
from .xbox import (
    XDVDFS_EXECUTABLE,
    XboxAdapter,
    XboxPlatformDetector,
)
from .xbox360 import (
    Xbox360PlatformDetector,
    Xbox360StructuralInspector,
)


@dataclass(frozen=True, slots=True)
class DefaultRuntimeConfig:
    """Configuration for the standard framework runtime composition."""

    allow_headerless_nes: bool = False
    dolphin_executable: str = DOLPHIN_EXECUTABLE
    dolphin_temporary_directory: Path | None = None
    xbox_executable: str = XDVDFS_EXECUTABLE
    xbox_temporary_directory: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.allow_headerless_nes, bool):
            raise TypeError(
                "allow_headerless_nes must be a boolean"
            )

        for attribute in (
            "dolphin_executable",
            "xbox_executable",
        ):
            value = getattr(self, attribute)

            if not isinstance(value, str):
                raise TypeError(
                    f"{attribute} must be a string"
                )

            normalized = value.strip()

            if not normalized:
                raise ValueError(
                    f"{attribute} must not be empty"
                )

            object.__setattr__(
                self,
                attribute,
                normalized,
            )

        for attribute in (
            "dolphin_temporary_directory",
            "xbox_temporary_directory",
        ):
            value = getattr(self, attribute)

            if value is not None:
                object.__setattr__(
                    self,
                    attribute,
                    Path(value),
                )


DEFAULT_RUNTIME_CONFIG = DefaultRuntimeConfig()


def build_default_detector(
    config: DefaultRuntimeConfig = DEFAULT_RUNTIME_CONFIG,
) -> CompositePlatformDetector:
    """Build the standard platform detector composition."""

    if not isinstance(config, DefaultRuntimeConfig):
        raise TypeError("config must be DefaultRuntimeConfig")

    return CompositePlatformDetector(
        (
            NesPlatformDetector(),
            Ps2PlatformDetector(),
            Ps3PlatformDetector(),
            DolphinPlatformDetector(
                executable=config.dolphin_executable,
            ),
            Xbox360PlatformDetector(),
            NintendoSwitchPlatformDetector(),
            XboxPlatformDetector(
                executable=config.xbox_executable,
            ),
        )
    )


def build_default_inspector(
    config: DefaultRuntimeConfig = DEFAULT_RUNTIME_CONFIG,
) -> CompositeStructuralInspector:
    """Build the standard non-normalizing structural inspector."""

    if not isinstance(config, DefaultRuntimeConfig):
        raise TypeError(
            "config must be DefaultRuntimeConfig"
        )

    return CompositeStructuralInspector(
        (
            Ps2StructuralInspector(),
            Ps3StructuralInspector(),
            Xbox360StructuralInspector(),
            NintendoSwitchStructuralInspector(),
        )
    )


def build_default_normalizer(
    config: DefaultRuntimeConfig = DEFAULT_RUNTIME_CONFIG,
) -> CompositeNormalizer:
    """Build the standard normalized-content adapter router.

    Headerless NES normalization remains explicit opt-in because a
    filename extension alone is not authoritative content evidence.
    """

    if not isinstance(config, DefaultRuntimeConfig):
        raise TypeError(
            "config must be DefaultRuntimeConfig"
        )

    return CompositeNormalizer(
        (
            NesAdapter(
                allow_headerless=config.allow_headerless_nes,
            ),
            DolphinAdapter(
                executable=config.dolphin_executable,
                temporary_directory=(
                    config.dolphin_temporary_directory
                ),
            ),
            XboxAdapter(
                executable=config.xbox_executable,
                temporary_directory=(
                    config.xbox_temporary_directory
                ),
            ),
        )
    )
