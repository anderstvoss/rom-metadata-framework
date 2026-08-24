from __future__ import annotations

import json

import pytest

from rom_metadata_framework.cli import main


def test_platforms_text_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["platforms"]) == 0

    output = capsys.readouterr().out

    assert (
        "PLATFORM\tDISPLAY_NAME\tMANUFACTURER"
        "\tSTATUS\tDETECT"
        in output
    )
    assert "\tINTEGRITY\tRCHEEVOS_MAP" in output
    assert "switch" in output
    assert "ps3" in output
    assert "snes" in output


def test_platforms_json_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(
        [
            "platforms",
            "--json",
        ]
    ) == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    by_platform = {
        item["platform"]: item
        for item in payload
    }

    assert (
        by_platform[
            "switch"
        ]["status"]
        == "supported"
    )

    assert (
        by_platform[
            "snes"
        ]["status"]
        == "registered"
    )

    assert (
        by_platform[
            "snes"
        ]["rcheevos_mapping"]
        is True
    )

    assert (
        by_platform[
            "switch"
        ]["rcheevos_mapping"]
        is False
    )

    assert (
        by_platform[
            "switch"
        ]["integrity"]
        == "none"
    )


def test_capabilities_text_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["capabilities"]) == 0

    output = capsys.readouterr().out

    assert "nes-normalization: ready" in output
    assert "dolphin-normalization:" in output
    assert "xbox-normalization:" in output


def test_capabilities_json_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(
        [
            "capabilities",
            "--json",
        ]
    ) == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert isinstance(payload, list)

    assert all(
        "name" in item
        and "status" in item
        for item in payload
    )


def test_cli_requires_command() -> None:
    with pytest.raises(
        SystemExit,
    ) as exc:
        main([])

    assert exc.value.code == 2


def test_inspect_missing_path_returns_operational_error(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "missing.bin"

    assert main(
        [
            "inspect",
            str(path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "path does not exist" in captured.err


def test_inspect_directory_returns_operational_error(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(
        [
            "inspect",
            str(tmp_path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "not a regular file" in captured.err


def test_inspect_unrecognized_file_returns_unresolved(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "ordinary.bin"
    path.write_bytes(b"not a supported rom")

    assert main(
        [
            "inspect",
            str(path),
        ]
    ) == 3

    output = capsys.readouterr().out

    assert "detected platform: unresolved" in output
    assert "structural inspection: unavailable" in output


def test_inspect_unrecognized_file_json(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "ordinary.bin"
    path.write_bytes(b"not a supported rom")

    assert main(
        [
            "inspect",
            str(path),
            "--json",
        ]
    ) == 3

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["path"] == str(path)
    assert payload["detected_platform"] is None
    assert payload["inspection"] is None
    assert "platform_detection" in payload


def test_jsonable_handles_framework_value_shapes() -> None:
    from dataclasses import dataclass
    from enum import StrEnum
    from pathlib import Path

    from rom_metadata_framework.cli import _jsonable

    class State(StrEnum):
        READY = "ready"

    @dataclass
    class Example:
        path: Path
        state: State
        values: tuple[int, ...]

    assert _jsonable(
        Example(
            path=Path("sample.bin"),
            state=State.READY,
            values=(1, 2),
        )
    ) == {
        "path": "sample.bin",
        "state": "ready",
        "values": [1, 2],
    }



def test_inspect_success_with_structural_metadata(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Keep the CLI test independent from private ROM data. Import the
    # established synthetic PS2 fixture builder used by the platform tests.
    from tests.unit.test_ps2 import _write_iso

    path = tmp_path / "synthetic.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\"
            b"SLUS_123.45;1\r\n"
        ),
    )

    assert main(
        [
            "inspect",
            str(path),
            "--json",
        ]
    ) == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert (
        payload["detected_platform"]
        == "ps2"
    )

    assert payload["inspection"] is not None

    assert (
        payload["inspection"][
            "physical_representation"
        ]["format"]
        == "iso9660"
    )

    assert (
        payload["inspection"][
            "local_metadata"
        ]
        is not None
    )


def test_inspect_success_text_output(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tests.unit.test_ps2 import _write_iso

    path = tmp_path / "synthetic.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\"
            b"SLUS_123.45;1\r\n"
        ),
    )

    assert main(
        [
            "inspect",
            str(path),
        ]
    ) == 0

    output = capsys.readouterr().out

    assert f"path: {path}" in output
    assert (
        "detected platform: ps2"
        in output
    )
    assert (
        "structural inspection: available"
        in output
    )
    assert "representation: iso9660" in output
    assert "local metadata: available" in output


def test_jsonable_mapping_and_fallback() -> None:
    from rom_metadata_framework.cli import _jsonable

    class StringOnly:
        def __str__(self) -> str:
            return "string-only-value"

    assert _jsonable(
        {
            "nested": (
                1,
                True,
                None,
            ),
        }
    ) == {
        "nested": [
            1,
            True,
            None,
        ],
    }

    assert (
        _jsonable(StringOnly())
        == "string-only-value"
    )


def test_inspection_text_without_local_metadata(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework.cli import (
        _print_inspection_text,
    )

    _print_inspection_text(
        {
            "path": "sample.bin",
            "detected_platform": "synthetic-platform",
            "inspection": {
                "physical_representation": {
                    "kind": "container",
                    "format": "synthetic-format",
                },
                "local_metadata": None,
            },
        }
    )

    output = capsys.readouterr().out

    assert (
        "detected platform: synthetic-platform"
        in output
    )
    assert (
        "representation: synthetic-format"
        in output
    )
    assert "local metadata: unavailable" in output


def _fake_identification_result(
    *,
    identified: bool,
    release_conflict: bool = False,
    platform_conflict: bool = False,
):
    from types import SimpleNamespace

    from rom_metadata_framework.canonical import (
        CanonicalReleaseIdentity,
    )

    candidate = SimpleNamespace(
        platform="ps2",
    )

    detection = SimpleNamespace(
        best=candidate,
        candidates=(candidate,),
    )

    canonical = (
        CanonicalReleaseIdentity(
            release_name="Synthetic Release",
            platform="ps2",
            source="synthetic-provider",
            source_id="synthetic-release-1",
        )
        if identified
        else None
    )

    return SimpleNamespace(
        identified=identified,
        physical_identity=SimpleNamespace(
            file_name="synthetic.iso",
            file_size=1234,
        ),
        platform_detection=detection,
        physical_match=canonical,
        physical_representation=None,
        local_metadata=None,
        normalized_content=None,
        normalized_match=None,
        release_reconciliation=None,
        platform_reconciliation=None,
        canonical_match=canonical,
        has_release_conflict=release_conflict,
        has_platform_conflict=platform_conflict,
    )


def test_identify_missing_path_returns_operational_error(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "missing.iso"

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "path does not exist" in captured.err


def test_identify_success_text_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.iso"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=True
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 0

    output = capsys.readouterr().out

    assert "Title:     Synthetic Release" in output
    assert "Platform:  PlayStation 2" in output
    assert "Format:    ISO" in output
    assert "identified:" not in output
    assert "provider match:" not in output


def test_identify_success_json_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.iso"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=True
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
            "--json",
        ]
    ) == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["status"] == "catalogue"
    assert payload["title"] == "Synthetic Release"
    assert payload["title_source"] == "catalogue"
    assert payload["platform"] == {
        "id": "ps2",
        "name": "PlayStation 2",
    }
    assert payload["format"] == "iso"

    assert "identified" not in payload
    assert "canonical_match" not in payload
    assert "platform_detection" not in payload


def test_identify_unresolved_exit_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=False
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 3

    output = capsys.readouterr().out

    assert "Platform:" in output
    assert "PlayStation 2" in output
    assert "Format:" in output
    assert "BIN" in output
    assert "Title:" not in output


def test_identify_conflict_exit_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=False,
        release_conflict=True,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
            "--json",
        ]
    ) == 4


def test_identify_no_normalize_passes_none(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=True
    )

    observed = {}

    def fake_identify_file(
        *args,
        **kwargs,
    ):
        observed.update(kwargs)
        return result

    monkeypatch.setattr(
        cli,
        "identify_file",
        fake_identify_file,
    )

    assert main(
        [
            "identify",
            str(path),
            "--no-normalize",
        ]
    ) == 0

    assert observed["normalizer"] is None


def test_identify_default_includes_normalizer(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=True
    )

    observed = {}

    def fake_identify_file(
        *args,
        **kwargs,
    ):
        observed.update(kwargs)
        return result

    monkeypatch.setattr(
        cli,
        "identify_file",
        fake_identify_file,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 0

    assert observed["normalizer"] is not None


def test_identify_provider_error_becomes_exit_5(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.playmatch import PlaymatchError

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise PlaymatchError(
            "synthetic provider failure"
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 5

    assert "Playmatch error" in (
        capsys.readouterr().err
    )


def test_identify_directory_returns_operational_error(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(
        [
            "identify",
            str(tmp_path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "not a regular file" in captured.err


def test_identify_provider_error_json(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.playmatch import (
        PlaymatchError,
    )

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise PlaymatchError(
            "synthetic provider failure"
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "identify",
            str(path),
            "--json",
        ]
    ) == 5

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["error"] == "provider-error"
    assert payload["provider"] == "playmatch"
    assert (
        payload["message"]
        == "synthetic provider failure"
    )


def test_identify_framework_contract_error_text(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.contracts import (
        FrameworkContractError,
    )

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise FrameworkContractError(
            "synthetic contract failure",
            component="synthetic-component",
            operation="synthetic-operation",
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "framework error:" in captured.err
    assert (
        "synthetic contract failure"
        in captured.err
    )


def test_identify_framework_contract_error_json(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.contracts import (
        FrameworkContractError,
    )

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise FrameworkContractError(
            "synthetic contract failure",
            component="synthetic-component",
            operation="synthetic-operation",
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "identify",
            str(path),
            "--json",
        ]
    ) == 5

    payload = json.loads(
        capsys.readouterr().out
    )

    assert (
        payload["error"]
        == "framework-contract-error"
    )
    assert (
        payload["message"]
        == "synthetic contract failure"
    )


def test_identify_io_error_text(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise OSError(
            "synthetic io failure"
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "synthetic io failure" in captured.err


def test_identify_io_error_json(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise OSError(
            "synthetic io failure"
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "identify",
            str(path),
            "--json",
        ]
    ) == 5

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["error"] == "io-error"
    assert payload["message"] == "synthetic io failure"


def test_identify_platform_conflict_exit_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=False,
        platform_conflict=True,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 4


def test_identification_text_renders_concise_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework.cli import (
        _print_identification_text,
    )

    _print_identification_text(
        {
            "title": "Synthetic Release",
            "platform": {
                "id": "wii",
                "name": "Wii",
            },
            "region": "USA",
            "identifier": {
                "type": "nintendo-game-id",
                "label": "Game ID",
                "value": "ABCE01",
            },
            "revision": "2",
            "disc": {
                "number": 1,
                "total": 2,
            },
            "format": "rvz",
        }
    )

    output = capsys.readouterr().out

    assert "Title:" in output
    assert "Synthetic Release" in output
    assert "Platform:" in output
    assert "Wii" in output
    assert "Region:" in output
    assert "USA" in output
    assert "Game ID:" in output
    assert "ABCE01" in output
    assert "Revision:" in output
    assert "2" in output
    assert "Disc:" in output
    assert "1 / 2" in output
    assert "Format:" in output
    assert "RVZ" in output


def _verification_identity(
    *,
    status: str | None = None,
    authority: str = "redump",
    current: bool | None = True,
    conflicts: tuple[str, ...] = (),
):
    from rom_metadata_framework.canonical import (
        CanonicalReleaseIdentity,
    )
    from rom_metadata_framework.provenance import (
        CatalogueEvidence,
    )

    evidence = ()

    if status is not None or authority:
        evidence = (
            CatalogueEvidence(
                source="synthetic-provider",
                catalogue_name="Synthetic Catalogue",
                authority=authority,
                file_status=status,
                match_method="SHA256",
                current_in_latest_catalogue=current,
            ),
        )

    return CanonicalReleaseIdentity(
        release_name="Synthetic Release",
        platform="ps2",
        source="synthetic-provider",
        source_id="synthetic-release-1",
        catalogue_evidence=evidence,
        conflicts=conflicts,
    )


def test_verify_missing_path_returns_operational_error(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "missing.iso"

    assert main(
        [
            "verify",
            str(path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "path does not exist" in captured.err


def test_verify_directory_returns_operational_error(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(
        [
            "verify",
            str(tmp_path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "not a regular file" in captured.err


def test_verify_unresolved_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=False
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "verify",
            str(path),
        ]
    ) == 3

    output = capsys.readouterr().out

    assert "canonical release: unresolved" in output
    assert "verification: unavailable" in output


def test_verify_known_good_text_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from types import SimpleNamespace

    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    identity = _verification_identity(
        status=None,
        authority="redump",
        current=True,
    )

    result = SimpleNamespace(
        canonical_match=identity,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "verify",
            str(path),
        ]
    ) == 0

    output = capsys.readouterr().out

    assert "canonical release: Synthetic Release" in output
    assert "verification: known_good" in output
    assert "reason:" in output


def test_verify_known_good_json_without_network(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from types import SimpleNamespace

    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    identity = _verification_identity(
        status=None,
        authority="redump",
        current=True,
    )

    result = SimpleNamespace(
        canonical_match=identity,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "verify",
            str(path),
            "--json",
        ]
    ) == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert (
        payload["canonical_match"][
            "release_name"
        ]
        == "Synthetic Release"
    )

    assert (
        payload["verification"]["status"]
        == "known_good"
    )


def test_verify_conflict_returns_exit_4(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from types import SimpleNamespace

    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    identity = _verification_identity(
        conflicts=(
            "synthetic conflict",
        )
    )

    result = SimpleNamespace(
        canonical_match=identity,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "verify",
            str(path),
        ]
    ) == 4

    output = capsys.readouterr().out

    assert "verification: conflict" in output
    assert "conflict: synthetic conflict" in output


def test_verify_no_normalize_passes_none(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    observed = {}

    def fake_identify_file(
        *args,
        **kwargs,
    ):
        observed.update(kwargs)
        return SimpleNamespace(
            canonical_match=None,
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fake_identify_file,
    )

    assert main(
        [
            "verify",
            str(path),
            "--no-normalize",
        ]
    ) == 3

    assert observed["normalizer"] is None


def test_verify_provider_error_json(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.playmatch import (
        PlaymatchError,
    )

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise PlaymatchError(
            "synthetic provider failure"
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "verify",
            str(path),
            "--json",
        ]
    ) == 5

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["error"] == "provider-error"
    assert payload["provider"] == "playmatch"


def test_verify_known_bad_returns_exit_4(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from types import SimpleNamespace

    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    identity = _verification_identity(
        status="bad",
        authority="redump",
        current=True,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: SimpleNamespace(
            canonical_match=identity,
        ),
    )

    assert main(
        [
            "verify",
            str(path),
        ]
    ) == 4

    output = capsys.readouterr().out

    assert "verification: known_bad" in output


def test_verify_catalogue_match_returns_unresolved(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from types import SimpleNamespace

    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    identity = _verification_identity(
        status=None,
        authority="untrusted-catalogue",
        current=True,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: SimpleNamespace(
            canonical_match=identity,
        ),
    )

    assert main(
        [
            "verify",
            str(path),
            "--json",
        ]
    ) == 3

    payload = json.loads(
        capsys.readouterr().out
    )

    assert (
        payload["verification"]["status"]
        == "catalogue_match"
    )


def test_verify_probable_returns_unresolved(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from types import SimpleNamespace

    from rom_metadata_framework import cli
    from rom_metadata_framework.canonical import (
        CanonicalReleaseIdentity,
        IdentificationEvidence,
    )

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    identity = CanonicalReleaseIdentity(
        release_name="Synthetic Release",
        platform="ps2",
        source="synthetic-provider",
        source_id="synthetic-release-1",
        evidence=(
            IdentificationEvidence(
                source="synthetic-source",
                method="product-code",
                value="SYNTHETIC-1",
            ),
        ),
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: SimpleNamespace(
            canonical_match=identity,
        ),
    )

    assert main(
        [
            "verify",
            str(path),
        ]
    ) == 3

    output = capsys.readouterr().out

    assert "verification: probable" in output


def test_verify_framework_contract_error_json(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.contracts import (
        FrameworkContractError,
    )

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise FrameworkContractError(
            "synthetic contract failure",
            component="synthetic-component",
            operation="synthetic-operation",
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "verify",
            str(path),
            "--json",
        ]
    ) == 5

    payload = json.loads(
        capsys.readouterr().out
    )

    assert (
        payload["error"]
        == "framework-contract-error"
    )
    assert (
        payload["message"]
        == "synthetic contract failure"
    )


def test_verify_io_error_text(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise OSError(
            "synthetic io failure"
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "verify",
            str(path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "synthetic io failure" in captured.err


def test_verify_provider_error_text(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.playmatch import (
        PlaymatchError,
    )

    path = tmp_path / "synthetic.bin"
    path.write_bytes(b"synthetic")

    def fail(*args, **kwargs):
        raise PlaymatchError(
            "synthetic provider failure"
        )

    monkeypatch.setattr(
        cli,
        "identify_file",
        fail,
    )

    assert main(
        [
            "verify",
            str(path),
        ]
    ) == 5

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "Playmatch error:" in captured.err


def test_identification_payload_uses_explicit_projection() -> None:
    from pathlib import Path

    from rom_metadata_framework.cli import (
        _identification_payload,
    )

    result = _fake_identification_result(
        identified=True
    )

    payload = _identification_payload(
        Path("synthetic.iso"),
        result,
    )

    assert payload["physical_identity"] == {
        "platform": None,
        "format": None,
        "file_name": "synthetic.iso",
        "file_size": 1234,
        "hashes": None,
        "serial": None,
        "product_code": None,
        "title_id": None,
        "specialized_identifiers": {},
        "media_metadata": {},
        "adapter": None,
    }

    assert payload["platform_detection"] == {
        "candidates": [
            {
                "platform": "ps2",
                "confidence": None,
                "evidence": [],
            },
        ],
    }

    assert (
        payload["canonical_match"][
            "release_name"
        ]
        == "Synthetic Release"
    )


def test_explicit_canonical_projection_ignores_extra_attributes() -> None:
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _canonical_release_payload,
    )

    value = SimpleNamespace(
        release_name="Synthetic Release",
        platform="ps2",
        source="synthetic-provider",
        source_id="synthetic-release-1",
        title=None,
        external_ids={},
        evidence=(),
        catalogue_evidence=(),
        conflicts=(),
        future_internal_field="must-not-leak",
    )

    payload = _canonical_release_payload(
        value
    )

    assert isinstance(payload, dict)
    assert (
        "future_internal_field"
        not in payload
    )


def test_explicit_verification_projection_ignores_extra_attributes() -> None:
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _verification_report_payload,
    )

    report = SimpleNamespace(
        status="known_good",
        evidence=(),
        reasons=("synthetic reason",),
        conflicts=(),
        future_internal_field="must-not-leak",
    )

    payload = _verification_report_payload(
        report
    )

    assert payload == {
        "status": "known_good",
        "evidence": [],
        "reasons": [
            "synthetic reason",
        ],
        "conflicts": [],
    }


def test_inspection_payload_uses_explicit_projection(
    tmp_path,
) -> None:
    from rom_metadata_framework.cli import (
        _inspection_payload,
    )
    from rom_metadata_framework.defaults import (
        DefaultRuntimeConfig,
        build_default_detector,
        build_default_inspector,
    )
    from tests.unit.test_ps2 import _write_iso

    path = tmp_path / "synthetic.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\"
            b"SLUS_123.45;1\r\n"
        ),
    )

    config = DefaultRuntimeConfig()
    detection = build_default_detector(
        config
    ).detect(path)
    inspection = build_default_inspector(
        config
    ).inspect(path)

    payload = _inspection_payload(
        path,
        detection=detection,
        inspection=inspection,
    )

    assert isinstance(
        payload["platform_detection"],
        dict,
    )
    assert isinstance(
        payload["inspection"],
        dict,
    )

    assert (
        payload["inspection"][
            "physical_representation"
        ]["format"]
        == "iso9660"
    )

    assert (
        payload["inspection"][
            "local_metadata"
        ]["platform"]
        == "ps2"
    )


def test_concise_identification_payload_projects_wii_evidence() -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _concise_identification_payload,
    )
    from rom_metadata_framework.identity import HashSet
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )
    from rom_metadata_framework.representation import (
        RepresentationIdentity,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = SimpleNamespace(
        canonical_match=SimpleNamespace(
            title="Synthetic Game",
            release_name="Synthetic Game (USA)",
            platform="wii",
        ),
        display_title="Synthetic Game",
        identification_strength="catalogue",
        title_source="catalogue",
        platform_detection=SimpleNamespace(
            best=SimpleNamespace(
                platform="wii",
            ),
        ),
        local_metadata=LocalContentMetadata(
            platform="wii",
            identifiers=(
                LocalIdentifier(
                    namespace="nintendo-game-id",
                    value="ABCE01",
                    provenance=provenance,
                ),
            ),
            release_revisions=(
                LocalMetadataValue(
                    value="0",
                    provenance=provenance,
                ),
            ),
            regions=(
                LocalMetadataValue(
                    value="USA",
                    provenance=provenance,
                ),
            ),
        ),
        physical_representation=RepresentationIdentity(
            kind="disc-image",
            format="rvz",
        ),
        physical_identity=SimpleNamespace(
            hashes=HashSet(
                crc32="12345678",
                md5="0" * 32,
                sha1="1" * 40,
                sha256="2" * 64,
            ),
        ),
        normalized_content=None,
        provider_name="playmatch",
        physical_lookup=SimpleNamespace(
            status="matched",
        ),
        normalized_lookup=SimpleNamespace(
            status="not_attempted",
        ),
    )

    payload = _concise_identification_payload(
        Path("synthetic.rvz"),
        result,
    )

    assert payload == {
        "path": "synthetic.rvz",
        "status": "catalogue",
        "title": "Synthetic Game",
        "title_source": "catalogue",
        "platform": {
            "id": "wii",
            "name": "Wii",
        },
        "region": "USA",
        "identifier": {
            "type": "nintendo-game-id",
            "label": "Game ID",
            "value": "ABCE01",
        },
        "format": "rvz",
        "hashes": {
            "physical": {
                "crc32": "12345678",
                "md5": "0" * 32,
                "sha1": "1" * 40,
                "sha256": "2" * 64,
            },
        },
        "provider": {
            "name": "playmatch",
            "physical": "matched",
            "normalized": "not_attempted",
        },
    }


def test_concise_identification_payload_adds_computed_disc_hashes() -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _concise_identification_payload,
    )
    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.identity import HashSet

    result = SimpleNamespace(
        canonical_match=None,
        display_title=None,
        identification_strength="unresolved",
        title_source="unavailable",
        platform_detection=SimpleNamespace(
            best=None,
        ),
        local_metadata=None,
        physical_representation=None,
        physical_identity=SimpleNamespace(
            hashes=HashSet(
                sha256="3" * 64,
            ),
        ),
        normalized_content=NormalizedContentIdentity(
            kind="disc",
            hashes=HashSet(
                crc32="87654321",
                md5="4" * 32,
                sha1="5" * 40,
            ),
        ),
        provider_name=None,
        physical_lookup=None,
        normalized_lookup=None,
    )

    payload = _concise_identification_payload(
        Path("synthetic.iso"),
        result,
    )

    assert payload["format"] == "iso"
    assert payload["hashes"] == {
        "physical": {
            "sha256": "3" * 64,
        },
        "disc": {
            "crc32": "87654321",
            "md5": "4" * 32,
            "sha1": "5" * 40,
        },
    }


def test_concise_identification_payload_uses_nondefault_revision_and_multidisc() -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _concise_identification_payload,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = SimpleNamespace(
        canonical_match=None,
        display_title="Embedded Game",
        identification_strength="local_strong",
        title_source="embedded",
        platform_detection=SimpleNamespace(
            best=SimpleNamespace(
                platform="wii",
            ),
        ),
        local_metadata=LocalContentMetadata(
            platform="wii",
            titles=(
                LocalMetadataValue(
                    value="Embedded Game",
                    provenance=provenance,
                ),
            ),
            release_revisions=(
                LocalMetadataValue(
                    value="2",
                    provenance=provenance,
                ),
            ),
            disc_numbers=(
                LocalMetadataValue(
                    value=1,
                    provenance=provenance,
                ),
            ),
            disc_totals=(
                LocalMetadataValue(
                    value=2,
                    provenance=provenance,
                ),
            ),
        ),
        physical_representation=None,
        physical_identity=SimpleNamespace(
            hashes=None,
        ),
        normalized_content=None,
        provider_name=None,
        physical_lookup=None,
        normalized_lookup=None,
    )

    payload = _concise_identification_payload(
        Path("synthetic.rvz"),
        result,
    )

    assert payload["title"] == "Embedded Game"
    assert payload["status"] == "local_strong"
    assert payload["revision"] == "2"
    assert payload["disc"] == {
        "number": 1,
        "total": 2,
    }


def test_concise_identification_primary_identifier_labels() -> None:
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _concise_primary_identifier,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    cases = (
        (
            "ps2",
            "ps2-product-code",
            "SLUS-20013",
            "Product Code",
        ),
        (
            "ps3",
            "ps3-title-id",
            "BLUS31011",
            "Title ID",
        ),
        (
            "xbox",
            "xbox-title-id",
            "4D530004",
            "Title ID",
        ),
        (
            "xbox360",
            "xbox360-title-id",
            "12345678",
            "Title ID",
        ),
        (
            "switch",
            "switch-application-id",
            "0100123456789000",
            "Application ID",
        ),
    )

    for (
        platform,
        namespace,
        value,
        label,
    ) in cases:
        result = SimpleNamespace(
            local_metadata=LocalContentMetadata(
                platform=platform,
                identifiers=(
                    LocalIdentifier(
                        namespace=namespace,
                        value=value,
                        provenance=provenance,
                    ),
                ),
            ),
        )

        assert _concise_primary_identifier(
            result,
            platform=platform,
        ) == {
            "type": namespace,
            "label": label,
            "value": value,
        }


def test_identify_complete_json_preserves_diagnostic_projection(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.iso"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=True
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
            "--json",
            "--complete",
        ]
    ) == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["identified"] is True
    assert payload["detected_platform"] == "ps2"
    assert (
        payload["canonical_match"][
            "release_name"
        ]
        == "Synthetic Release"
    )
    assert "physical_identity" in payload
    assert "platform_detection" in payload


def test_identify_hashes_renders_physical_and_disc_hashes(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.identity import HashSet

    path = tmp_path / "synthetic.iso"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=True
    )

    result.physical_identity.hashes = HashSet(
        sha256="a" * 64,
    )
    result.normalized_content = NormalizedContentIdentity(
        kind="disc",
        hashes=HashSet(
            crc32="12345678",
            md5="b" * 32,
            sha1="c" * 40,
        ),
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
            "--hashes",
        ]
    ) == 0

    output = capsys.readouterr().out

    assert "Physical file hashes:" in output
    assert f"SHA256: {'a' * 64}" in output

    assert "Disc hashes:" in output
    assert "CRC32: 12345678" in output
    assert f"MD5: {'b' * 32}" in output
    assert f"SHA1: {'c' * 40}" in output


def test_identify_default_text_hides_hashes(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.identity import HashSet

    path = tmp_path / "synthetic.iso"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=True
    )

    result.physical_identity.hashes = HashSet(
        sha256="d" * 64,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 0

    output = capsys.readouterr().out

    assert "Physical file hashes:" not in output
    assert "SHA256:" not in output


def test_identify_local_strong_returns_success(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rom_metadata_framework import cli

    path = tmp_path / "synthetic.iso"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=False
    )

    result.identification_strength = "local_strong"

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
        ]
    ) == 0


def test_identify_complete_requires_json(
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "synthetic.iso"
    path.write_bytes(b"synthetic")

    with pytest.raises(
        SystemExit
    ) as exc_info:
        main(
            [
                "identify",
                str(path),
                "--complete",
            ]
        )

    assert exc_info.value.code == 2

    captured = capsys.readouterr()

    assert captured.out == ""
    assert (
        "--complete requires --json"
        in captured.err
    )


def test_concise_format_prefers_physical_source_extension() -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _concise_identification_payload,
    )
    from rom_metadata_framework.representation import (
        RepresentationIdentity,
    )

    cases = (
        (
            "ps2",
            "iso9660",
            "game.iso",
            "iso",
        ),
        (
            "ps3",
            "iso9660",
            "game.iso",
            "iso",
        ),
        (
            "xbox360",
            "xbox360-xgd",
            "game.iso",
            "iso",
        ),
        (
            "wii",
            "rvz",
            "game.rvz",
            "rvz",
        ),
    )

    for (
        platform,
        representation_format,
        filename,
        expected,
    ) in cases:
        result = SimpleNamespace(
            canonical_match=None,
            display_title=None,
            identification_strength="local_strong",
            title_source="unavailable",
            platform_detection=SimpleNamespace(
                best=SimpleNamespace(
                    platform=platform,
                ),
            ),
            local_metadata=None,
            physical_representation=RepresentationIdentity(
                kind="disc-image",
                format=representation_format,
            ),
            physical_identity=SimpleNamespace(
                hashes=None,
            ),
            normalized_content=None,
            provider_name=None,
            physical_lookup=None,
            normalized_lookup=None,
        )

        payload = _concise_identification_payload(
            Path(filename),
            result,
        )

        assert payload["format"] == expected


def test_concise_format_falls_back_to_representation_without_extension() -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _concise_identification_payload,
    )
    from rom_metadata_framework.representation import (
        RepresentationIdentity,
    )

    result = SimpleNamespace(
        canonical_match=None,
        display_title=None,
        identification_strength="local_probable",
        title_source="unavailable",
        platform_detection=SimpleNamespace(
            best=None,
        ),
        local_metadata=None,
        physical_representation=RepresentationIdentity(
            kind="disc-image",
            format="xiso",
        ),
        physical_identity=SimpleNamespace(
            hashes=None,
        ),
        normalized_content=None,
        provider_name=None,
        physical_lookup=None,
        normalized_lookup=None,
    )

    payload = _concise_identification_payload(
        Path("extensionless"),
        result,
    )

    assert payload["format"] == "xiso"


def test_identify_hashes_with_json_is_redundant_but_valid(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rom_metadata_framework import cli
    from rom_metadata_framework.identity import HashSet

    path = tmp_path / "synthetic.iso"
    path.write_bytes(b"synthetic")

    result = _fake_identification_result(
        identified=True
    )

    result.physical_identity.hashes = HashSet(
        sha256="e" * 64,
    )

    monkeypatch.setattr(
        cli,
        "identify_file",
        lambda *args, **kwargs: result,
    )

    assert main(
        [
            "identify",
            str(path),
            "--json",
            "--hashes",
        ]
    ) == 0

    payload = json.loads(
        capsys.readouterr().out
    )

    assert payload["hashes"] == {
        "physical": {
            "sha256": "e" * 64,
        },
    }


def test_concise_json_preserves_provider_unavailable_status() -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _concise_identification_payload,
    )

    result = SimpleNamespace(
        canonical_match=None,
        display_title=None,
        identification_strength="local_strong",
        title_source="unavailable",
        platform_detection=SimpleNamespace(
            best=SimpleNamespace(
                platform="ps2",
            ),
        ),
        local_metadata=None,
        physical_representation=None,
        physical_identity=SimpleNamespace(
            hashes=None,
        ),
        normalized_content=None,
        provider_name="playmatch",
        physical_lookup=SimpleNamespace(
            status="unavailable",
        ),
        normalized_lookup=SimpleNamespace(
            status="not_attempted",
        ),
    )

    payload = _concise_identification_payload(
        Path("game.iso"),
        result,
    )

    assert payload["status"] == "local_strong"
    assert payload["provider"] == {
        "name": "playmatch",
        "physical": "unavailable",
        "normalized": "not_attempted",
    }


def test_concise_region_prefers_country_over_broad_region() -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from rom_metadata_framework.cli import (
        _concise_identification_payload,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = SimpleNamespace(
        canonical_match=None,
        display_title=None,
        identification_strength="local_strong",
        title_source="unavailable",
        platform_detection=SimpleNamespace(
            best=SimpleNamespace(
                platform="wii",
            ),
        ),
        local_metadata=LocalContentMetadata(
            platform="wii",
            regions=(
                LocalMetadataValue(
                    value="NTSC-U",
                    provenance=provenance,
                ),
            ),
            countries=(
                LocalMetadataValue(
                    value="USA",
                    provenance=provenance,
                ),
            ),
        ),
        physical_representation=None,
        physical_identity=SimpleNamespace(
            hashes=None,
        ),
        normalized_content=None,
        provider_name=None,
        physical_lookup=None,
        normalized_lookup=None,
    )

    payload = _concise_identification_payload(
        Path("game.rvz"),
        result,
    )

    assert payload["region"] == "USA"
