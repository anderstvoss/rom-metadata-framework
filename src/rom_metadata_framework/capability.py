from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from .backends import BackendStatus


class RuntimeCapabilityStatus(StrEnum):
    """Operational state of one optional or built-in capability."""

    READY = "ready"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RuntimeCapability:
    """Provider-independent report of one runtime capability."""

    name: str
    status: RuntimeCapabilityStatus
    backend: str | None = None
    version: str | None = None
    reason: str | None = None
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = self.name.strip()

        if not name:
            raise ValueError("capability name must not be empty")

        object.__setattr__(self, "name", name)

        for attribute in (
            "backend",
            "version",
            "reason",
        ):
            value = getattr(self, attribute)

            if value is not None:
                object.__setattr__(
                    self,
                    attribute,
                    value.strip() or None,
                )

        normalized_details = {
            str(key).strip(): str(value).strip()
            for key, value in self.details.items()
        }

        if any(not key for key in normalized_details):
            raise ValueError(
                "capability detail keys must not be empty"
            )

        object.__setattr__(
            self,
            "details",
            MappingProxyType(normalized_details),
        )

    @property
    def ready(self) -> bool:
        """Whether the capability is operational."""

        return self.status is RuntimeCapabilityStatus.READY


def capability_from_backend_status(
    capability_name: str,
    backend: BackendStatus,
) -> RuntimeCapability:
    """Translate backend discovery/probe state into runtime capability."""

    details = {}

    if backend.executable is not None:
        details["executable"] = str(backend.executable)

    if not backend.available:
        return RuntimeCapability(
            name=capability_name,
            status=RuntimeCapabilityStatus.UNAVAILABLE,
            backend=backend.name,
            reason=backend.error,
            details=details,
        )

    if backend.error is not None:
        return RuntimeCapability(
            name=capability_name,
            status=RuntimeCapabilityStatus.ERROR,
            backend=backend.name,
            version=backend.version,
            reason=backend.error,
            details=details,
        )

    return RuntimeCapability(
        name=capability_name,
        status=RuntimeCapabilityStatus.READY,
        backend=backend.name,
        version=backend.version,
        details=details,
    )
