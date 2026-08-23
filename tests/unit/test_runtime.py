from rom_metadata_framework.capability import (
    RuntimeCapability,
    RuntimeCapabilityStatus,
)
from rom_metadata_framework.runtime import (
    RuntimeReport,
    build_default_runtime_report,
    report_runtime,
)


def capability(
    name: str,
    status: RuntimeCapabilityStatus,
) -> RuntimeCapability:
    return RuntimeCapability(
        name=name,
        status=status,
    )


def test_runtime_report_groups_capabilities_by_status() -> None:
    report = RuntimeReport(
        capabilities=(
            capability("ready", RuntimeCapabilityStatus.READY),
            capability(
                "unavailable",
                RuntimeCapabilityStatus.UNAVAILABLE,
            ),
            capability("error", RuntimeCapabilityStatus.ERROR),
            capability("unknown", RuntimeCapabilityStatus.UNKNOWN),
        ),
    )

    assert tuple(item.name for item in report.ready) == ("ready",)
    assert tuple(item.name for item in report.unavailable) == (
        "unavailable",
    )
    assert tuple(item.name for item in report.errors) == ("error",)
    assert tuple(item.name for item in report.unknown) == ("unknown",)


def test_runtime_report_fully_ready_requires_all_ready() -> None:
    report = RuntimeReport(
        capabilities=(
            capability("one", RuntimeCapabilityStatus.READY),
            capability("two", RuntimeCapabilityStatus.READY),
        ),
    )

    assert report.fully_ready
    assert not report.has_errors


def test_runtime_report_unavailable_prevents_full_readiness() -> None:
    report = RuntimeReport(
        capabilities=(
            capability("one", RuntimeCapabilityStatus.READY),
            capability(
                "two",
                RuntimeCapabilityStatus.UNAVAILABLE,
            ),
        ),
    )

    assert not report.fully_ready
    assert not report.has_errors


def test_runtime_report_unknown_prevents_full_readiness() -> None:
    report = RuntimeReport(
        capabilities=(
            capability("one", RuntimeCapabilityStatus.READY),
            capability("two", RuntimeCapabilityStatus.UNKNOWN),
        ),
    )

    assert not report.fully_ready
    assert not report.has_errors


def test_runtime_report_error_sets_has_errors() -> None:
    report = RuntimeReport(
        capabilities=(
            capability("one", RuntimeCapabilityStatus.READY),
            capability("two", RuntimeCapabilityStatus.ERROR),
        ),
    )

    assert not report.fully_ready
    assert report.has_errors


def test_empty_runtime_report_is_not_fully_ready() -> None:
    report = RuntimeReport(capabilities=())

    assert not report.fully_ready
    assert not report.has_errors


def test_report_runtime_preserves_reporter_order() -> None:
    class Reporter:
        def runtime_capabilities(self):
            return (
                capability("first", RuntimeCapabilityStatus.READY),
                capability("second", RuntimeCapabilityStatus.UNKNOWN),
            )

    report = report_runtime(Reporter())

    assert tuple(item.name for item in report.capabilities) == (
        "first",
        "second",
    )


def test_default_runtime_report_exposes_independent_capabilities() -> None:
    report = build_default_runtime_report(
        dolphin_executable="/definitely/missing/dolphin-tool",
    )

    assert tuple(item.name for item in report.capabilities) == (
        "nes-normalization",
        "dolphin-normalization",
    )

    assert tuple(item.name for item in report.ready) == (
        "nes-normalization",
    )
    assert tuple(item.name for item in report.unavailable) == (
        "dolphin-normalization",
    )
    assert not report.fully_ready
    assert not report.has_errors
