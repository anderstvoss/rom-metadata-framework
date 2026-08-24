import json
from pathlib import Path

import pytest

from rom_metadata_framework.adapters import IdentificationAdapter
from rom_metadata_framework.rcheevos import (
    RcheevosAdapter,
    RcheevosResponseError,
)


def write_fake_helper(
    path: Path,
    payload: object,
) -> Path:
    serialized = json.dumps(payload)

    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"hash\" ]; then\n"
        f"  printf '%s\\n' '{serialized}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n"
    )

    path.chmod(0o755)
    return path


def valid_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "console_id": 3,
        "hash": "cdd3c8c37322978ca8669b34bc89c804",
        "backend": "rcheevos",
        "backend_version": "12.4",
    }


def test_rcheevos_adapter_matches_identification_protocol(
    tmp_path: Path,
) -> None:
    helper = write_fake_helper(
        tmp_path / "helper",
        valid_payload(),
    )

    adapter = RcheevosAdapter(
        console_id=3,
        platform="snes",
        executable=str(helper),
    )

    assert isinstance(adapter, IdentificationAdapter)


def test_rcheevos_adapter_identifies_specialized_hash(
    tmp_path: Path,
) -> None:
    helper = write_fake_helper(
        tmp_path / "helper",
        valid_payload(),
    )

    rom = tmp_path / "example.SFC"
    rom.write_bytes(b"synthetic-test-data")

    identity = RcheevosAdapter(
        console_id=3,
        platform="snes",
        executable=str(helper),
    ).identify(rom)

    assert identity.platform == "snes"
    assert identity.format == "sfc"
    assert (
        identity.specialized_identifiers["retroachievements"]
        == "cdd3c8c37322978ca8669b34bc89c804"
    )

    assert identity.hashes.md5 is None

    assert identity.adapter is not None
    assert identity.file_name == rom.name
    assert identity.file_size == rom.stat().st_size
    assert identity.adapter.name == "rcheevos"
    assert identity.adapter.version == "12.4"
    assert identity.adapter.backend == "rom-metadata-rcheevos"


def test_rcheevos_adapter_rejects_invalid_console_id() -> None:
    with pytest.raises(ValueError):
        RcheevosAdapter(console_id=0)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("console_id", 4),
        ("backend", "unexpected"),
        ("hash", "not-a-valid-hash"),
        ("backend_version", ""),
    ],
)
def test_rcheevos_adapter_rejects_invalid_response_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payload = valid_payload()
    payload[field] = value

    helper = write_fake_helper(
        tmp_path / "helper",
        payload,
    )

    rom = tmp_path / "example.sfc"
    rom.write_bytes(b"synthetic-test-data")

    adapter = RcheevosAdapter(
        console_id=3,
        executable=str(helper),
    )

    with pytest.raises(RcheevosResponseError):
        adapter.identify(rom)


def test_rcheevos_adapter_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    helper = tmp_path / "helper"

    helper.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'not-json'\n"
        "exit 0\n"
    )
    helper.chmod(0o755)

    rom = tmp_path / "example.sfc"
    rom.write_bytes(b"synthetic-test-data")

    adapter = RcheevosAdapter(
        console_id=3,
        executable=str(helper),
    )

    with pytest.raises(RcheevosResponseError):
        adapter.identify(rom)


def test_rcheevos_adapter_supports_regular_files(
    tmp_path: Path,
) -> None:
    rom = tmp_path / "example.sfc"
    rom.write_bytes(b"synthetic-test-data")

    adapter = RcheevosAdapter(console_id=3)

    assert adapter.supports(rom) is True
    assert adapter.supports(tmp_path / "missing.sfc") is False


def test_adapter_for_platform_uses_canonical_name() -> None:
    from rom_metadata_framework.rcheevos import adapter_for_platform

    adapter = adapter_for_platform("super-nintendo")

    assert adapter.console_id == 3
    assert adapter.platform == "snes"


def test_adapter_for_platform_accepts_common_alias() -> None:
    from rom_metadata_framework.rcheevos import adapter_for_platform

    adapter = adapter_for_platform("gba")

    assert adapter.console_id == 5
    assert adapter.platform == "gba"
