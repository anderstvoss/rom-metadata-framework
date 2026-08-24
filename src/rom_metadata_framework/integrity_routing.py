from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .contracts import IntegrityVerifierContractError
from .integrity import (
    IntegrityProbe,
    IntegrityReport,
    IntegrityVerifier,
)


class IntegrityRoutingError(RuntimeError):
    """Base class for specialist integrity routing failures."""


class NoSupportingIntegrityVerifierError(
    IntegrityRoutingError
):
    """Raised when no verifier supports a physical artifact."""


class IntegrityProbeFailureError(
    IntegrityRoutingError
):
    """Raised when probing fails without a positive verifier."""

    def __init__(
        self,
        path: Path,
        probes: Sequence[IntegrityProbe],
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
            f"{probe.verifier}={probe.status.value}"
            for probe in self.probes
        )

        super().__init__(
            "integrity probing failed for "
            f"{self.path.name!r}: {summary}"
        )


class AmbiguousIntegrityVerifierError(
    IntegrityRoutingError
):
    """Raised when multiple verifiers claim one artifact."""

    def __init__(
        self,
        path: Path,
        verifier_names: Sequence[str],
    ) -> None:
        self.path = Path(path)
        self.verifier_names = tuple(
            verifier_names
        )

        super().__init__(
            "multiple integrity verifiers support "
            f"{self.path.name!r}: "
            + ", ".join(self.verifier_names)
        )


class CompositeIntegrityVerifier:
    """Route one artifact to exactly one specialist verifier."""

    name = "composite"

    def __init__(
        self,
        verifiers: Sequence[IntegrityVerifier],
    ) -> None:
        candidates = tuple(verifiers)

        if any(
            not isinstance(
                verifier,
                IntegrityVerifier,
            )
            for verifier in candidates
        ):
            raise IntegrityVerifierContractError(
                (
                    "all verifiers must implement "
                    "IntegrityVerifier"
                ),
                component="CompositeIntegrityVerifier",
                operation="register",
            )

        names = tuple(
            verifier.name.strip()
            for verifier in candidates
        )

        if any(not name for name in names):
            raise ValueError(
                "integrity verifier names must not be empty"
            )

        if len(set(names)) != len(names):
            raise ValueError(
                "integrity verifier names must be unique"
            )

        self.verifiers = candidates

    def probe_verifiers(
        self,
        path: Path,
    ) -> tuple[
        tuple[IntegrityVerifier, IntegrityProbe],
        ...,
    ]:
        """Probe every verifier while preserving diagnostics."""

        path = Path(path)
        results = []

        for verifier in self.verifiers:
            probe = verifier.probe(path)

            if not isinstance(
                probe,
                IntegrityProbe,
            ):
                raise IntegrityVerifierContractError(
                    (
                        "integrity probe() must return "
                        "IntegrityProbe"
                    ),
                    component=verifier.name,
                    operation="probe",
                )

            if probe.verifier != verifier.name.strip():
                raise IntegrityVerifierContractError(
                    (
                        "integrity probe verifier name does not "
                        "match registered verifier name"
                    ),
                    component=verifier.name,
                    operation="probe",
                    field="verifier",
                )

            results.append(
                (
                    verifier,
                    probe,
                )
            )

        return tuple(results)

    def select(
        self,
        path: Path,
    ) -> IntegrityVerifier:
        """Select exactly one applicable specialist verifier."""

        path = Path(path)
        probes = self.probe_verifiers(path)

        matches = tuple(
            verifier
            for verifier, probe in probes
            if probe.supported
        )

        if len(matches) > 1:
            raise AmbiguousIntegrityVerifierError(
                path,
                tuple(
                    verifier.name
                    for verifier in matches
                ),
            )

        if len(matches) == 1:
            return matches[0]

        terminal = tuple(
            probe
            for _, probe in probes
            if probe.terminal_failure
        )

        if terminal:
            raise IntegrityProbeFailureError(
                path,
                terminal,
            )

        raise NoSupportingIntegrityVerifierError(
            "no integrity verifier supports "
            f"{path.name!r}"
        )

    def verify(
        self,
        path: Path,
    ) -> IntegrityReport:
        """Verify through the only applicable specialist verifier."""

        verifier = self.select(path)
        report = verifier.verify(
            Path(path)
        )

        if not isinstance(
            report,
            IntegrityReport,
        ):
            raise IntegrityVerifierContractError(
                (
                    "integrity verify() must return "
                    "IntegrityReport"
                ),
                component=verifier.name,
                operation="verify",
            )

        if report.verifier != verifier.name.strip():
            raise IntegrityVerifierContractError(
                (
                    "integrity report verifier name does not "
                    "match registered verifier name"
                ),
                component=verifier.name,
                operation="verify",
                field="verifier",
            )

        return report
