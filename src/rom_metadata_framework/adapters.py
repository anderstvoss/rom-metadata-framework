from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .identity import RomIdentity


@runtime_checkable
class IdentificationAdapter(Protocol):
    """Interface implemented by ROM identification backends."""

    @property
    def name(self) -> str:
        """Stable adapter name."""
        ...

    def supports(self, path: Path) -> bool:
        """Return whether this adapter can inspect the supplied path."""
        ...

    def identify(self, path: Path) -> RomIdentity:
        """Inspect a ROM or image and return normalized identity information."""
        ...
