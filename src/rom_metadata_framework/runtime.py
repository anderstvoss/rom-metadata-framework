from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .capability import (
    RuntimeCapability,
    RuntimeCapabilityStatus,
)
from .defaults import build_default_normalizer
from .dolphin import DOLPHIN_EXECUTABLE


class CapabilityReporter(Protocol):
    """Object exposing runtime capability information."""

    def runtime_capabilities(
        self,
    ) -> tuple[RuntimeCapability, ...]:
        """Return constituent runtime capabilities."""
        ...


@dataclass(frozen=True, slots=True)
class RuntimeReport:
    """Framework-level snapshot of runtime capability state."""

    capabilities: tuple[RuntimeCapability, ...]

    @property
    def ready(self) -> tuple[RuntimeCapability, ...]:
        return tuple(
            capability
            for capability in self.capabilities
            if capability.status is RuntimeCapabilityStatus.READY
        )

    @property
    def unavailable(self) -> tuple[RuntimeCapability, ...]:
        return tuple(
            capability
            for capability in self.capabilities
            if capability.status is RuntimeCapabilityStatus.UNAVAILABLE
        )

    @property
    def errors(self) -> tuple[RuntimeCapability, ...]:
        return tuple(
            capability
            for capability in self.capabilities
            if capability.status is RuntimeCapabilityStatus.ERROR
        )

    @property
    def unknown(self) -> tuple[RuntimeCapability, ...]:
        return tuple(
            capability
            for capability in self.capabilities
            if capability.status is RuntimeCapabilityStatus.UNKNOWN
        )

    @property
    def fully_ready(self) -> bool:
        """Whether every reported capability is explicitly ready."""

        return bool(self.capabilities) and all(
            capability.ready
            for capability in self.capabilities
        )

    @property
    def has_errors(self) -> bool:
        """Whether any capability reports an operational error."""

        return bool(self.errors)


def report_runtime(
    reporter: CapabilityReporter,
) -> RuntimeReport:
    """Build a runtime report from a capability-reporting component."""

    return RuntimeReport(
        capabilities=tuple(reporter.runtime_capabilities()),
    )


def build_default_runtime_report(
    *,
    allow_headerless_nes: bool = False,
    dolphin_executable: str = DOLPHIN_EXECUTABLE,
    dolphin_temporary_directory: Path | None = None,
) -> RuntimeReport:
    """Report runtime state for the standard normalizer configuration."""

    normalizer = build_default_normalizer(
        allow_headerless_nes=allow_headerless_nes,
        dolphin_executable=dolphin_executable,
        dolphin_temporary_directory=dolphin_temporary_directory,
    )

    return report_runtime(normalizer)
