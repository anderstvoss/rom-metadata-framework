from __future__ import annotations

from pathlib import Path

import pytest

from rom_metadata_framework.integrity import (
    IntegrityEvidence,
    IntegrityProbe,
    IntegrityProbeStatus,
    IntegrityReport,
    IntegrityStatus,
)
from rom_metadata_framework.integrity_routing import (
    AmbiguousIntegrityVerifierError,
    CompositeIntegrityVerifier,
    IntegrityProbeFailureError,
    NoSupportingIntegrityVerifierError,
)


class FakeVerifier:
    def __init__(
        self,
        name: str,
        status: IntegrityProbeStatus,
    ) -> None:
        self._name = name
        self._status = status

    @property
    def name(self) -> str:
        return self._name

    def probe(
        self,
        path: Path,
    ) -> IntegrityProbe:
        del path

        return IntegrityProbe(
            verifier=self.name,
            status=self._status,
        )

    def verify(
        self,
        path: Path,
    ) -> IntegrityReport:
        del path

        return IntegrityReport(
            platform="ps3",
            verifier=self.name,
            status=IntegrityStatus.VERIFIED,
            evidence=(
                IntegrityEvidence(
                    source=self.name,
                    method="synthetic-check",
                    result="valid",
                ),
            ),
        )


def test_integrity_report_canonicalizes_platform() -> None:
    report = IntegrityReport(
        platform="playstation-3",
        verifier="synthetic",
        status=IntegrityStatus.VERIFIED,
    )

    assert report.platform == "ps3"
    assert report.verified


def test_integrity_evidence_normalizes_fields() -> None:
    evidence = IntegrityEvidence(
        source=" Synthetic ",
        method=" Sector Check ",
        result=" valid ",
        details={
            " sector ": " 12 ",
        },
    )

    assert evidence.source == "synthetic"
    assert evidence.method == "sector check"
    assert evidence.result == "valid"
    assert evidence.details == {
        "sector": "12",
    }


def test_empty_router_is_unsupported(
    tmp_path: Path,
) -> None:
    router = CompositeIntegrityVerifier(())

    with pytest.raises(
        NoSupportingIntegrityVerifierError
    ):
        router.verify(
            tmp_path / "example.bin"
        )


def test_router_selects_only_supported_verifier(
    tmp_path: Path,
) -> None:
    router = CompositeIntegrityVerifier(
        (
            FakeVerifier(
                "unsupported",
                IntegrityProbeStatus.UNSUPPORTED,
            ),
            FakeVerifier(
                "supported",
                IntegrityProbeStatus.SUPPORTED,
            ),
        )
    )

    report = router.verify(
        tmp_path / "example.bin"
    )

    assert report.verifier == "supported"
    assert report.status is IntegrityStatus.VERIFIED


def test_router_rejects_ambiguous_support(
    tmp_path: Path,
) -> None:
    router = CompositeIntegrityVerifier(
        (
            FakeVerifier(
                "first",
                IntegrityProbeStatus.SUPPORTED,
            ),
            FakeVerifier(
                "second",
                IntegrityProbeStatus.SUPPORTED,
            ),
        )
    )

    with pytest.raises(
        AmbiguousIntegrityVerifierError
    ):
        router.verify(
            tmp_path / "example.bin"
        )


def test_router_surfaces_probe_failure(
    tmp_path: Path,
) -> None:
    router = CompositeIntegrityVerifier(
        (
            FakeVerifier(
                "backend",
                IntegrityProbeStatus.BACKEND_UNAVAILABLE,
            ),
        )
    )

    with pytest.raises(
        IntegrityProbeFailureError
    ):
        router.verify(
            tmp_path / "example.bin"
        )


def test_positive_verifier_wins_over_unrelated_probe_failure(
    tmp_path: Path,
) -> None:
    router = CompositeIntegrityVerifier(
        (
            FakeVerifier(
                "broken-optional",
                IntegrityProbeStatus.BACKEND_FAILURE,
            ),
            FakeVerifier(
                "supported",
                IntegrityProbeStatus.SUPPORTED,
            ),
        )
    )

    report = router.verify(
        tmp_path / "example.bin"
    )

    assert report.verifier == "supported"


def test_integrity_evidence_rejects_empty_source() -> None:
    with pytest.raises(
        ValueError,
        match="source",
    ):
        IntegrityEvidence(
            source=" ",
            method="check",
            result="valid",
        )


def test_integrity_evidence_rejects_empty_method() -> None:
    with pytest.raises(
        ValueError,
        match="method",
    ):
        IntegrityEvidence(
            source="test",
            method=" ",
            result="valid",
        )


def test_integrity_evidence_rejects_empty_result() -> None:
    with pytest.raises(
        ValueError,
        match="result",
    ):
        IntegrityEvidence(
            source="test",
            method="check",
            result=" ",
        )


def test_integrity_evidence_rejects_empty_detail_key() -> None:
    with pytest.raises(
        ValueError,
        match="detail keys",
    ):
        IntegrityEvidence(
            source="test",
            method="check",
            result="valid",
            details={
                " ": "value",
            },
        )


def test_integrity_report_rejects_empty_verifier() -> None:
    with pytest.raises(
        ValueError,
        match="verifier name",
    ):
        IntegrityReport(
            platform="ps3",
            verifier=" ",
            status=IntegrityStatus.INCONCLUSIVE,
        )


def test_integrity_report_normalizes_reasons() -> None:
    report = IntegrityReport(
        platform="ps3",
        verifier="test",
        status=IntegrityStatus.INCONCLUSIVE,
        reasons=(
            " first ",
            " ",
            "second",
        ),
    )

    assert report.reasons == (
        "first",
        "second",
    )


def test_integrity_probe_rejects_empty_verifier() -> None:
    with pytest.raises(
        ValueError,
        match="verifier name",
    ):
        IntegrityProbe(
            verifier=" ",
            status=IntegrityProbeStatus.UNSUPPORTED,
        )


def test_integrity_probe_rejects_empty_detail_key() -> None:
    with pytest.raises(
        ValueError,
        match="detail keys",
    ):
        IntegrityProbe(
            verifier="test",
            status=IntegrityProbeStatus.UNSUPPORTED,
            details={
                " ": "value",
            },
        )


def test_integrity_probe_normalizes_reason() -> None:
    probe = IntegrityProbe(
        verifier="test",
        status=IntegrityProbeStatus.UNSUPPORTED,
        reason=" unsupported format ",
    )

    assert probe.reason == "unsupported format"


def test_integrity_probe_status_properties() -> None:
    supported = IntegrityProbe(
        verifier="supported",
        status=IntegrityProbeStatus.SUPPORTED,
    )
    unavailable = IntegrityProbe(
        verifier="unavailable",
        status=IntegrityProbeStatus.BACKEND_UNAVAILABLE,
    )
    unsupported = IntegrityProbe(
        verifier="unsupported",
        status=IntegrityProbeStatus.UNSUPPORTED,
    )

    assert supported.supported
    assert not supported.terminal_failure

    assert not unavailable.supported
    assert unavailable.terminal_failure

    assert not unsupported.supported
    assert not unsupported.terminal_failure


def test_router_rejects_nonverifier_registration() -> None:
    from rom_metadata_framework.contracts import (
        IntegrityVerifierContractError,
    )

    with pytest.raises(
        IntegrityVerifierContractError,
    ) as exc_info:
        CompositeIntegrityVerifier(
            (object(),)
        )

    assert (
        exc_info.value.component
        == "CompositeIntegrityVerifier"
    )
    assert exc_info.value.operation == "register"


def test_router_rejects_empty_verifier_name() -> None:
    class EmptyNameVerifier(FakeVerifier):
        @property
        def name(self) -> str:
            return " "

    with pytest.raises(
        ValueError,
        match="names must not be empty",
    ):
        CompositeIntegrityVerifier(
            (
                EmptyNameVerifier(
                    "ignored",
                    IntegrityProbeStatus.UNSUPPORTED,
                ),
            )
        )


def test_router_rejects_duplicate_verifier_names() -> None:
    with pytest.raises(
        ValueError,
        match="names must be unique",
    ):
        CompositeIntegrityVerifier(
            (
                FakeVerifier(
                    "same",
                    IntegrityProbeStatus.UNSUPPORTED,
                ),
                FakeVerifier(
                    "same",
                    IntegrityProbeStatus.UNSUPPORTED,
                ),
            )
        )


def test_probe_failure_requires_probes() -> None:
    with pytest.raises(
        ValueError,
        match="at least one",
    ):
        IntegrityProbeFailureError(
            Path("example.bin"),
            (),
        )


def test_probe_failure_rejects_nonterminal_probe() -> None:
    with pytest.raises(
        ValueError,
        match="terminal probes",
    ):
        IntegrityProbeFailureError(
            Path("example.bin"),
            (
                IntegrityProbe(
                    verifier="test",
                    status=IntegrityProbeStatus.UNSUPPORTED,
                ),
            ),
        )


def test_router_rejects_invalid_probe_type(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.contracts import (
        IntegrityVerifierContractError,
    )

    class BadProbeVerifier(FakeVerifier):
        def probe(
            self,
            path: Path,
        ) -> object:
            del path
            return object()

    router = CompositeIntegrityVerifier(
        (
            BadProbeVerifier(
                "bad",
                IntegrityProbeStatus.UNSUPPORTED,
            ),
        )
    )

    with pytest.raises(
        IntegrityVerifierContractError,
    ) as exc_info:
        router.select(
            tmp_path / "example.bin"
        )

    assert exc_info.value.component == "bad"
    assert exc_info.value.operation == "probe"


def test_router_rejects_probe_name_mismatch(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.contracts import (
        IntegrityVerifierContractError,
    )

    class WrongNameVerifier(FakeVerifier):
        def probe(
            self,
            path: Path,
        ) -> IntegrityProbe:
            del path

            return IntegrityProbe(
                verifier="different",
                status=IntegrityProbeStatus.UNSUPPORTED,
            )

    router = CompositeIntegrityVerifier(
        (
            WrongNameVerifier(
                "registered",
                IntegrityProbeStatus.UNSUPPORTED,
            ),
        )
    )

    with pytest.raises(
        IntegrityVerifierContractError,
    ) as exc_info:
        router.select(
            tmp_path / "example.bin"
        )

    assert exc_info.value.field == "verifier"


def test_router_rejects_invalid_report_type(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.contracts import (
        IntegrityVerifierContractError,
    )

    class BadReportVerifier(FakeVerifier):
        def verify(
            self,
            path: Path,
        ) -> object:
            del path
            return object()

    router = CompositeIntegrityVerifier(
        (
            BadReportVerifier(
                "bad-report",
                IntegrityProbeStatus.SUPPORTED,
            ),
        )
    )

    with pytest.raises(
        IntegrityVerifierContractError,
    ) as exc_info:
        router.verify(
            tmp_path / "example.bin"
        )

    assert exc_info.value.operation == "verify"


def test_router_rejects_report_name_mismatch(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.contracts import (
        IntegrityVerifierContractError,
    )

    class WrongReportNameVerifier(FakeVerifier):
        def verify(
            self,
            path: Path,
        ) -> IntegrityReport:
            del path

            return IntegrityReport(
                platform="ps3",
                verifier="different",
                status=IntegrityStatus.VERIFIED,
            )

    router = CompositeIntegrityVerifier(
        (
            WrongReportNameVerifier(
                "registered",
                IntegrityProbeStatus.SUPPORTED,
            ),
        )
    )

    with pytest.raises(
        IntegrityVerifierContractError,
    ) as exc_info:
        router.verify(
            tmp_path / "example.bin"
        )

    assert exc_info.value.field == "verifier"
