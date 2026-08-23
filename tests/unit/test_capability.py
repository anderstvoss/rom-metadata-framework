from pathlib import Path

import pytest

from rom_metadata_framework.backends import BackendStatus
from rom_metadata_framework.capability import (
    RuntimeCapability,
    RuntimeCapabilityStatus,
    capability_from_backend_status,
)


def test_ready_capability_reports_ready() -> None:
    capability = RuntimeCapability(
        name="nes-normalization",
        status=RuntimeCapabilityStatus.READY,
    )

    assert capability.ready


def test_non_ready_capabilities_are_not_ready() -> None:
    for status in (
        RuntimeCapabilityStatus.UNAVAILABLE,
        RuntimeCapabilityStatus.ERROR,
        RuntimeCapabilityStatus.UNKNOWN,
    ):
        capability = RuntimeCapability(
            name="example",
            status=status,
        )

        assert not capability.ready


def test_capability_normalizes_text_and_details() -> None:
    capability = RuntimeCapability(
        name="  dolphin-normalization  ",
        status=RuntimeCapabilityStatus.READY,
        backend="  dolphin  ",
        version="  2606a  ",
        details={" executable ": " /usr/bin/dolphin-tool "},
    )

    assert capability.name == "dolphin-normalization"
    assert capability.backend == "dolphin"
    assert capability.version == "2606a"
    assert capability.details == {
        "executable": "/usr/bin/dolphin-tool",
    }


def test_capability_details_are_immutable() -> None:
    capability = RuntimeCapability(
        name="example",
        status=RuntimeCapabilityStatus.READY,
        details={"key": "value"},
    )

    with pytest.raises(TypeError):
        capability.details["other"] = "value"


def test_empty_capability_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        RuntimeCapability(
            name="  ",
            status=RuntimeCapabilityStatus.READY,
        )


def test_missing_backend_maps_to_unavailable() -> None:
    capability = capability_from_backend_status(
        "dolphin-normalization",
        BackendStatus(
            name="dolphin",
            available=False,
            error="executable was not found",
        ),
    )

    assert capability.status is RuntimeCapabilityStatus.UNAVAILABLE
    assert not capability.ready
    assert capability.backend == "dolphin"
    assert capability.reason == "executable was not found"


def test_discovered_backend_error_maps_to_error() -> None:
    capability = capability_from_backend_status(
        "dolphin-normalization",
        BackendStatus(
            name="dolphin",
            available=True,
            executable=Path("/usr/bin/dolphin-tool"),
            error="version probe failed",
        ),
    )

    assert capability.status is RuntimeCapabilityStatus.ERROR
    assert not capability.ready
    assert capability.details["executable"] == "/usr/bin/dolphin-tool"


def test_discovered_backend_without_error_maps_to_ready() -> None:
    capability = capability_from_backend_status(
        "dolphin-normalization",
        BackendStatus(
            name="dolphin",
            available=True,
            executable=Path("/usr/bin/dolphin-tool"),
            version="Dolphin 2606a",
        ),
    )

    assert capability.status is RuntimeCapabilityStatus.READY
    assert capability.ready
    assert capability.version == "Dolphin 2606a"


def test_available_does_not_imply_operational() -> None:
    backend = BackendStatus(
        name="dolphin",
        available=True,
        executable=Path("/usr/bin/dolphin-tool"),
        error="backend invocation failed",
    )

    capability = capability_from_backend_status(
        "dolphin-normalization",
        backend,
    )

    assert backend.available
    assert not capability.ready
    assert capability.status is RuntimeCapabilityStatus.ERROR
