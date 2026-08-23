from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from .content import NormalizedContentIdentity


class NormalizerRoutingError(RuntimeError):
    """Base class for normalized-content routing failures."""


class NoSupportingNormalizerError(NormalizerRoutingError):
    """Raised when no registered normalizer supports a source file."""


class AmbiguousNormalizerError(NormalizerRoutingError):
    """Raised when multiple normalizers claim the same source file."""

    def __init__(
        self,
        path: Path,
        adapter_names: Sequence[str],
    ) -> None:
        self.path = Path(path)
        self.adapter_names = tuple(adapter_names)

        names = ", ".join(self.adapter_names)

        super().__init__(
            f"multiple normalizers support "
            f"{self.path.name!r}: {names}"
        )


class NormalizedResult(Protocol):
    """Result exposing normalized content identity."""

    @property
    def content(self) -> NormalizedContentIdentity:
        """Normalized content represented by the source."""
        ...


class RoutedNormalizer(Protocol):
    """Normalizer that can conservatively claim supported files."""

    @property
    def name(self) -> str:
        """Stable normalizer name."""
        ...

    def supports(self, path: Path) -> bool:
        """Return whether this normalizer claims the path."""
        ...

    def identify(self, path: Path) -> NormalizedResult:
        """Return normalized content represented by the path."""
        ...


class CompositeNormalizer:
    """Route one source file to exactly one supporting normalizer."""

    name = "composite"

    def __init__(
        self,
        normalizers: Sequence[RoutedNormalizer],
    ) -> None:
        self.normalizers = tuple(normalizers)

        names = [
            normalizer.name.strip()
            for normalizer in self.normalizers
        ]

        if any(not name for name in names):
            raise ValueError(
                "normalizer names must not be empty"
            )

        if len(set(names)) != len(names):
            raise ValueError(
                "normalizer names must be unique"
            )

    def supporting_normalizers(
        self,
        path: Path,
    ) -> tuple[RoutedNormalizer, ...]:
        """Return every registered normalizer claiming the path."""

        path = Path(path)

        return tuple(
            normalizer
            for normalizer in self.normalizers
            if normalizer.supports(path)
        )

    def select(
        self,
        path: Path,
    ) -> RoutedNormalizer:
        """Select exactly one normalizer or raise explicitly."""

        path = Path(path)
        matches = self.supporting_normalizers(path)

        if not matches:
            raise NoSupportingNormalizerError(
                f"no normalizer supports {path.name!r}"
            )

        if len(matches) > 1:
            raise AmbiguousNormalizerError(
                path,
                tuple(
                    normalizer.name
                    for normalizer in matches
                ),
            )

        return matches[0]

    def identify(
        self,
        path: Path,
    ) -> NormalizedResult:
        """Normalize through the only adapter claiming the source."""

        path = Path(path)

        return self.select(path).identify(path)
