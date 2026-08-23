import pytest

from rom_metadata_framework.normalization import (
    NormalizerProbe,
    NormalizerProbeStatus,
)


@pytest.mark.parametrize(
    ("status", "supported"),
    (
        (
            NormalizerProbeStatus.UNSUPPORTED,
            False,
        ),
        (
            NormalizerProbeStatus.SUPPORTED,
            True,
        ),
        (
            NormalizerProbeStatus.UNSAFE,
            False,
        ),
        (
            NormalizerProbeStatus.BACKEND_UNAVAILABLE,
            False,
        ),
        (
            NormalizerProbeStatus.BACKEND_FAILURE,
            False,
        ),
    ),
)
def test_probe_supported_property(
    status: NormalizerProbeStatus,
    supported: bool,
) -> None:
    probe = NormalizerProbe(
        normalizer="example",
        status=status,
    )

    assert probe.supported is supported


@pytest.mark.parametrize(
    ("status", "terminal"),
    (
        (
            NormalizerProbeStatus.UNSUPPORTED,
            False,
        ),
        (
            NormalizerProbeStatus.SUPPORTED,
            False,
        ),
        (
            NormalizerProbeStatus.UNSAFE,
            True,
        ),
        (
            NormalizerProbeStatus.BACKEND_UNAVAILABLE,
            True,
        ),
        (
            NormalizerProbeStatus.BACKEND_FAILURE,
            True,
        ),
    ),
)
def test_probe_terminal_failure_property(
    status: NormalizerProbeStatus,
    terminal: bool,
) -> None:
    probe = NormalizerProbe(
        normalizer="example",
        status=status,
    )

    assert probe.terminal_failure is terminal


def test_probe_normalizes_name_reason_and_details() -> None:
    probe = NormalizerProbe(
        normalizer=" example ",
        status=NormalizerProbeStatus.UNSAFE,
        reason=" malformed source ",
        details={
            " format ": " nes2 ",
        },
    )

    assert probe.normalizer == "example"
    assert probe.reason == "malformed source"
    assert dict(probe.details) == {
        "format": "nes2",
    }


def test_probe_details_are_immutable() -> None:
    probe = NormalizerProbe(
        normalizer="example",
        status=NormalizerProbeStatus.SUPPORTED,
        details={
            "format": "example",
        },
    )

    with pytest.raises(TypeError):
        probe.details["format"] = "changed"


def test_probe_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        NormalizerProbe(
            normalizer=" ",
            status=NormalizerProbeStatus.UNSUPPORTED,
        )
