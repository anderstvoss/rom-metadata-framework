from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .capability import (
    RuntimeCapability,
    RuntimeCapabilityStatus,
)
from .defaults import (
    DEFAULT_RUNTIME_CONFIG,
    DefaultRuntimeConfig,
    build_default_normalizer,
)


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
            capability.ready for capability in self.capabilities
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
    config: DefaultRuntimeConfig = DEFAULT_RUNTIME_CONFIG,
) -> RuntimeReport:
    """Report runtime state for the standard normalizer configuration."""

    return report_runtime(
        build_default_normalizer(config)
    )
