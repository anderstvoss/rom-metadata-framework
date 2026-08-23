from __future__ import annotations

from pathlib import Path

from .dolphin import (
    DOLPHIN_EXECUTABLE,
    DolphinAdapter,
)
from .nes import NesAdapter
from .routing import CompositeNormalizer
from .xbox import (
    XDVDFS_EXECUTABLE,
    XboxAdapter,
)


def build_default_normalizer(
    *,
    allow_headerless_nes: bool = False,
    dolphin_executable: str = DOLPHIN_EXECUTABLE,
    dolphin_temporary_directory: Path | None = None,
    xbox_executable: str = XDVDFS_EXECUTABLE,
    xbox_temporary_directory: Path | None = None,
) -> CompositeNormalizer:
    """Build the standard normalized-content adapter router.

    Headerless NES normalization remains explicit opt-in because a
    filename extension alone is not authoritative content evidence.
    """

    return CompositeNormalizer(
        (
            NesAdapter(
                allow_headerless=allow_headerless_nes,
            ),
            DolphinAdapter(
                executable=dolphin_executable,
                temporary_directory=dolphin_temporary_directory,
            ),
            XboxAdapter(
                executable=xbox_executable,
                temporary_directory=xbox_temporary_directory,
            ),
        )
    )
