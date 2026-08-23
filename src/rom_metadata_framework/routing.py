from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from .capability import (
    RuntimeCapability,
    RuntimeCapabilityStatus,
)
from .content import NormalizedContentIdentity
from .normalization import (
    NormalizerProbe,
    NormalizerProbeStatus,
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

    def runtime_capabilities(
        self,
    ) -> tuple[RuntimeCapability, ...]:
        """Report constituent runtime capabilities in registration order."""

        capabilities = []

        for normalizer in self.normalizers:
            capability_method = getattr(
                normalizer,
                "runtime_capability",
                None,
            )

            if callable(capability_method):
                capability = capability_method()
            else:
                capability = RuntimeCapability(
                    name=f"{normalizer.name}-normalization",
                    status=RuntimeCapabilityStatus.UNKNOWN,
                    reason=(
                        "normalizer does not expose runtime "
                        "capability information"
                    ),
                )

            capabilities.append(capability)

        return tuple(capabilities)

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
            probe_method = getattr(
                normalizer,
                "probe",
                None,
            )

            if callable(probe_method):
                probe = probe_method(path)
            else:
                supported = normalizer.supports(path)

                probe = NormalizerProbe(
                    normalizer=normalizer.name,
                    status=(
                        NormalizerProbeStatus.SUPPORTED
                        if supported
                        else NormalizerProbeStatus.UNSUPPORTED
                    ),
                )

            if probe.normalizer != normalizer.name.strip():
                raise ValueError(
                    "normalizer probe name does not match "
                    "registered normalizer name"
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
    ) -> NormalizedResult:
        """Normalize through the only adapter safely claiming the source."""

        path = Path(path)

        return self.select(path).identify(path)
