from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from .capability import (
    RuntimeCapability,
)
from .contracts import NormalizerContractError
from .normalization import (
    NormalizationResult,
    NormalizerProbe,
)


class NormalizerRoutingError(RuntimeError):
    """Base class for normalized-content routing failures."""


class NoSupportingNormalizerError(NormalizerRoutingError):
    """Raised when no registered normalizer supports a source file."""


class NormalizerProbeFailureError(NormalizerRoutingError):
    """Raised when routing cannot proceed because probing failed."""

    def __init__(
        self,
        path: Path,
        probes: Sequence[NormalizerProbe],
    ) -> None:
        self.path = Path(path)
        self.probes = tuple(probes)

        if not self.probes:
            raise ValueError(
                "probe failure requires at least one probe"
            )

        if any(
            not probe.terminal_failure
            for probe in self.probes
        ):
            raise ValueError(
                "probe failure may contain only terminal probes"
            )

        summary = ", ".join(
            f"{probe.normalizer}={probe.status.value}"
            for probe in self.probes
        )

        super().__init__(
            f"normalizer probing failed for "
            f"{self.path.name!r}: {summary}"
        )


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


@runtime_checkable
class RoutedNormalizer(Protocol):
    """Complete contract for a conservatively routed normalizer."""

    @property
    def name(self) -> str:
        """Stable normalizer name."""
        ...

    def runtime_capability(self) -> RuntimeCapability:
        """Report whether normalization dependencies are ready."""
        ...

    def probe(self, path: Path) -> NormalizerProbe:
        """Classify whether this normalizer can safely handle a path."""
        ...

    def identify(self, path: Path) -> NormalizationResult:
        """Return complete normalization evidence for the path."""
        ...


class CompositeNormalizer:
    """Route one source file to exactly one supporting normalizer."""

    name = "composite"

    def __init__(
        self,
        normalizers: Sequence[RoutedNormalizer],
    ) -> None:
        candidates = tuple(normalizers)

        if any(
            not isinstance(normalizer, RoutedNormalizer)
            for normalizer in candidates
        ):
            raise NormalizerContractError(
                (
                    "all normalizers must implement the "
                    "RoutedNormalizer contract"
                ),
                component="CompositeNormalizer",
                operation="register",
            )

        self.normalizers = candidates

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

    def runtime_capabilities(
        self,
    ) -> tuple[RuntimeCapability, ...]:
        """Report constituent runtime capabilities in registration order."""

        return tuple(
            normalizer.runtime_capability()
            for normalizer in self.normalizers
        )

    def probe_normalizers(
        self,
        path: Path,
    ) -> tuple[
        tuple[RoutedNormalizer, NormalizerProbe],
        ...,
    ]:
        """Probe every registered normalizer without losing diagnostics."""

        path = Path(path)
        results = []

        for normalizer in self.normalizers:
            probe = normalizer.probe(path)

            if not isinstance(probe, NormalizerProbe):
                raise NormalizerContractError(
                    "normalizer probe() must return NormalizerProbe",
                    component=normalizer.name,
                    operation="probe",
                )

            if probe.normalizer != normalizer.name.strip():
                raise NormalizerContractError(
                    (
                        "normalizer probe name does not match "
                        "registered normalizer name"
                    ),
                    component=normalizer.name,
                    operation="probe",
                    field="normalizer",
                )

            results.append(
                (
                    normalizer,
                    probe,
                )
            )

        return tuple(results)

    def supporting_normalizers(
        self,
        path: Path,
    ) -> tuple[RoutedNormalizer, ...]:
        """Return every registered normalizer safely claiming the path."""

        return tuple(
            normalizer
            for normalizer, probe
            in self.probe_normalizers(path)
            if probe.supported
        )

    def select(
        self,
        path: Path,
    ) -> RoutedNormalizer:
        """Select exactly one safe normalizer or raise explicitly."""

        path = Path(path)
        probes = self.probe_normalizers(path)

        matches = tuple(
            normalizer
            for normalizer, probe in probes
            if probe.supported
        )

        if len(matches) > 1:
            raise AmbiguousNormalizerError(
                path,
                tuple(
                    normalizer.name
                    for normalizer in matches
                ),
            )

        # A positive claim can proceed even when another optional
        # adapter could not complete its own probe. This preserves
        # usable independent normalization paths.
        if len(matches) == 1:
            return matches[0]

        terminal = tuple(
            probe
            for _, probe in probes
            if probe.terminal_failure
        )

        if terminal:
            raise NormalizerProbeFailureError(
                path,
                terminal,
            )

        raise NoSupportingNormalizerError(
            f"no normalizer supports {path.name!r}"
        )

    def identify(
        self,
        path: Path,
    ) -> NormalizationResult:
        """Normalize through the only adapter safely claiming the source."""

        path = Path(path)

        return self.select(path).identify(path)
