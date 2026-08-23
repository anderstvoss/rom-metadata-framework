from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .contracts import InspectionContractError
from .local_metadata import LocalContentMetadata
from .representation import RepresentationIdentity


@dataclass(frozen=True, slots=True)
class StructuralInspectionResult:
    """Non-normalizing structural evidence extracted from one artifact."""

    physical_representation: RepresentationIdentity | None = None
    local_metadata: LocalContentMetadata | None = None

    def __post_init__(self) -> None:
        if (
            self.physical_representation is None
            and self.local_metadata is None
        ):
            raise ValueError(
                "structural inspection must return at least one "
                "evidence component"
            )


@runtime_checkable
class StructuralInspector(Protocol):
    """Adapter that extracts structural evidence without normalization."""

    @property
    def name(self) -> str:
        """Stable inspector name."""
        ...

    def inspect(
        self,
        path: Path,
    ) -> StructuralInspectionResult | None:
        """Return structural evidence, or None when unsupported."""
        ...


class AmbiguousStructuralInspectorError(RuntimeError):
    """Raised when multiple inspectors claim the same source file."""

    def __init__(
        self,
        path: Path,
        inspector_names: Sequence[str],
    ) -> None:
        self.path = Path(path)
        self.inspector_names = tuple(inspector_names)

        super().__init__(
            "multiple structural inspectors support "
            f"{self.path.name!r}: "
            + ", ".join(self.inspector_names)
        )


class CompositeStructuralInspector:
    """Collect exactly one applicable structural inspection result."""

    name = "composite"

    def __init__(
        self,
        inspectors: Sequence[StructuralInspector],
    ) -> None:
        candidates = tuple(inspectors)

        if any(
            not isinstance(inspector, StructuralInspector)
            for inspector in candidates
        ):
            raise InspectionContractError(
                (
                    "all inspectors must implement the "
                    "StructuralInspector contract"
                ),
                component="CompositeStructuralInspector",
                operation="register",
            )

        names = tuple(
            inspector.name.strip()
            for inspector in candidates
        )

        if any(not name for name in names):
            raise ValueError(
                "structural inspector names must not be empty"
            )

        if len(set(names)) != len(names):
            raise ValueError(
                "structural inspector names must be unique"
            )

        self.inspectors = candidates

    def inspect(
        self,
        path: Path,
    ) -> StructuralInspectionResult | None:
        """Return the only structural result claiming this source."""

        path = Path(path)
        matches: list[
            tuple[StructuralInspector, StructuralInspectionResult]
        ] = []

        for inspector in self.inspectors:
            result = inspector.inspect(path)

            if result is None:
                continue

            if not isinstance(
                result,
                StructuralInspectionResult,
            ):
                raise InspectionContractError(
                    (
                        "inspector inspect() must return "
                        "StructuralInspectionResult or None"
                    ),
                    component=inspector.name,
                    operation="inspect",
                )

            matches.append(
                (
                    inspector,
                    result,
                )
            )

        if len(matches) > 1:
            raise AmbiguousStructuralInspectorError(
                path,
                tuple(
                    inspector.name
                    for inspector, _ in matches
                ),
            )

        if not matches:
            return None

        return matches[0][1]
