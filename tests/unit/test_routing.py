from dataclasses import dataclass
from pathlib import Path

import pytest

from rom_metadata_framework.content import (
    NormalizedContentIdentity,
)
from rom_metadata_framework.routing import (
    AmbiguousNormalizerError,
    CompositeNormalizer,
    NoSupportingNormalizerError,
)


@dataclass(frozen=True)
class FakeResult:
    content: NormalizedContentIdentity


class FakeNormalizer:
    def __init__(
        self,
        name: str,
        *,
        supports: bool,
    ) -> None:
        self.name = name
        self._supports = supports
        self.identify_calls = 0

    def supports(self, path: Path) -> bool:
        return self._supports

    def identify(self, path: Path) -> FakeResult:
        self.identify_calls += 1

        return FakeResult(
            content=NormalizedContentIdentity(
                kind=self.name,
            ),
        )


def test_composite_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError):
        CompositeNormalizer(
            (
                FakeNormalizer(
                    "duplicate",
                    supports=False,
                ),
                FakeNormalizer(
                    "duplicate",
                    supports=False,
                ),
            )
        )


def test_composite_zero_matches_is_explicit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unknown.bin"
    path.write_bytes(b"unknown")

    first = FakeNormalizer(
        "first",
        supports=False,
    )
    second = FakeNormalizer(
        "second",
        supports=False,
    )

    router = CompositeNormalizer(
        (first, second)
    )

    assert router.supporting_normalizers(path) == ()

    with pytest.raises(NoSupportingNormalizerError):
        router.select(path)

    with pytest.raises(NoSupportingNormalizerError):
        router.identify(path)

    assert first.identify_calls == 0
    assert second.identify_calls == 0


def test_composite_routes_exactly_one_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.bin"
    path.write_bytes(b"game")

    first = FakeNormalizer(
        "first",
        supports=False,
    )
    second = FakeNormalizer(
        "second",
        supports=True,
    )

    router = CompositeNormalizer(
        (first, second)
    )

    assert router.supporting_normalizers(path) == (
        second,
    )
    assert router.select(path) is second

    result = router.identify(path)

    assert result.content.kind == "second"
    assert first.identify_calls == 0
    assert second.identify_calls == 1


def test_composite_rejects_ambiguous_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ambiguous.bin"
    path.write_bytes(b"ambiguous")

    first = FakeNormalizer(
        "first",
        supports=True,
    )
    second = FakeNormalizer(
        "second",
        supports=True,
    )

    router = CompositeNormalizer(
        (first, second)
    )

    assert router.supporting_normalizers(path) == (
        first,
        second,
    )

    with pytest.raises(
        AmbiguousNormalizerError,
    ) as exc_info:
        router.identify(path)

    assert exc_info.value.adapter_names == (
        "first",
        "second",
    )
    assert first.identify_calls == 0
    assert second.identify_calls == 0


def test_composite_selection_is_not_order_fallback(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ambiguous.bin"
    path.write_bytes(b"ambiguous")

    first = FakeNormalizer(
        "first",
        supports=True,
    )
    second = FakeNormalizer(
        "second",
        supports=True,
    )

    router = CompositeNormalizer(
        (second, first)
    )

    with pytest.raises(AmbiguousNormalizerError):
        router.identify(path)

    assert first.identify_calls == 0
    assert second.identify_calls == 0


class FakeProbeNormalizer:
    def __init__(
        self,
        name: str,
        status,
    ) -> None:
        self.name = name
        self.status = status
        self.identify_calls = 0

    def probe(self, path: Path):
        from rom_metadata_framework.normalization import (
            NormalizerProbe,
        )

        return NormalizerProbe(
            normalizer=self.name,
            status=self.status,
        )

    def supports(self, path: Path) -> bool:
        return self.probe(path).supported

    def identify(self, path: Path) -> FakeResult:
        self.identify_calls += 1

        return FakeResult(
            content=NormalizedContentIdentity(
                kind=self.name,
            ),
        )


def test_composite_terminal_probe_failure_is_explicit(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbeStatus,
    )
    from rom_metadata_framework.routing import (
        NormalizerProbeFailureError,
    )

    path = tmp_path / "source.bin"
    path.write_bytes(b"source")

    unsafe = FakeProbeNormalizer(
        "unsafe",
        NormalizerProbeStatus.UNSAFE,
    )
    unavailable = FakeProbeNormalizer(
        "unavailable",
        NormalizerProbeStatus.BACKEND_UNAVAILABLE,
    )
    unsupported = FakeProbeNormalizer(
        "unsupported",
        NormalizerProbeStatus.UNSUPPORTED,
    )

    router = CompositeNormalizer(
        (
            unsafe,
            unavailable,
            unsupported,
        )
    )

    with pytest.raises(
        NormalizerProbeFailureError,
    ) as exc_info:
        router.select(path)

    assert tuple(
        probe.normalizer
        for probe in exc_info.value.probes
    ) == (
        "unsafe",
        "unavailable",
    )

    assert tuple(
        probe.status
        for probe in exc_info.value.probes
    ) == (
        NormalizerProbeStatus.UNSAFE,
        NormalizerProbeStatus.BACKEND_UNAVAILABLE,
    )

    assert unsafe.identify_calls == 0
    assert unavailable.identify_calls == 0
    assert unsupported.identify_calls == 0


def test_composite_supported_claim_wins_over_other_probe_failure(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbeStatus,
    )

    path = tmp_path / "source.bin"
    path.write_bytes(b"source")

    supported = FakeProbeNormalizer(
        "supported",
        NormalizerProbeStatus.SUPPORTED,
    )
    unavailable = FakeProbeNormalizer(
        "unavailable",
        NormalizerProbeStatus.BACKEND_UNAVAILABLE,
    )

    router = CompositeNormalizer(
        (
            supported,
            unavailable,
        )
    )

    assert router.select(path) is supported

    result = router.identify(path)

    assert result.content.kind == "supported"
    assert supported.identify_calls == 1
    assert unavailable.identify_calls == 0


def test_composite_ambiguity_precedes_unrelated_probe_failure(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbeStatus,
    )

    path = tmp_path / "source.bin"
    path.write_bytes(b"source")

    first = FakeProbeNormalizer(
        "first",
        NormalizerProbeStatus.SUPPORTED,
    )
    second = FakeProbeNormalizer(
        "second",
        NormalizerProbeStatus.SUPPORTED,
    )
    failed = FakeProbeNormalizer(
        "failed",
        NormalizerProbeStatus.BACKEND_FAILURE,
    )

    router = CompositeNormalizer(
        (
            first,
            failed,
            second,
        )
    )

    with pytest.raises(
        AmbiguousNormalizerError,
    ) as exc_info:
        router.select(path)

    assert exc_info.value.adapter_names == (
        "first",
        "second",
    )

    assert first.identify_calls == 0
    assert second.identify_calls == 0
    assert failed.identify_calls == 0


def test_composite_probe_results_preserve_all_adapter_outcomes(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbeStatus,
    )

    path = tmp_path / "source.bin"
    path.write_bytes(b"source")

    adapters = (
        FakeProbeNormalizer(
            "unsupported",
            NormalizerProbeStatus.UNSUPPORTED,
        ),
        FakeProbeNormalizer(
            "supported",
            NormalizerProbeStatus.SUPPORTED,
        ),
        FakeProbeNormalizer(
            "unsafe",
            NormalizerProbeStatus.UNSAFE,
        ),
    )

    results = CompositeNormalizer(
        adapters
    ).probe_normalizers(path)

    assert tuple(
        (
            normalizer.name,
            probe.status,
        )
        for normalizer, probe in results
    ) == (
        (
            "unsupported",
            NormalizerProbeStatus.UNSUPPORTED,
        ),
        (
            "supported",
            NormalizerProbeStatus.SUPPORTED,
        ),
        (
            "unsafe",
            NormalizerProbeStatus.UNSAFE,
        ),
    )


def test_composite_reports_runtime_capabilities_in_registration_order() -> None:
    from rom_metadata_framework.capability import (
        RuntimeCapability,
        RuntimeCapabilityStatus,
    )

    class CapabilityNormalizer:
        def __init__(self, name: str) -> None:
            self.name = name

        def runtime_capability(self) -> RuntimeCapability:
            return RuntimeCapability(
                name=f"{self.name}-normalization",
                status=RuntimeCapabilityStatus.READY,
            )

        def supports(self, path: Path) -> bool:
            return False

        def identify(self, path: Path):
            raise AssertionError("must not identify")

    router = CompositeNormalizer(
        (
            CapabilityNormalizer("first"),
            CapabilityNormalizer("second"),
        )
    )

    capabilities = router.runtime_capabilities()

    assert tuple(item.name for item in capabilities) == (
        "first-normalization",
        "second-normalization",
    )
    assert all(item.ready for item in capabilities)


def test_legacy_normalizer_runtime_capability_is_unknown() -> None:
    from rom_metadata_framework.capability import RuntimeCapabilityStatus

    class LegacyNormalizer:
        name = "legacy"

        def supports(self, path: Path) -> bool:
            return False

        def identify(self, path: Path):
            raise AssertionError("must not identify")

    router = CompositeNormalizer((LegacyNormalizer(),))

    capability = router.runtime_capabilities()[0]

    assert capability.name == "legacy-normalization"
    assert capability.status is RuntimeCapabilityStatus.UNKNOWN
    assert not capability.ready
    assert capability.reason is not None
