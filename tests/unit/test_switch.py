from pathlib import Path

import pytest

from rom_metadata_framework.switch import (
    NintendoSwitchFormatError,
    NintendoSwitchPlatformDetector,
    NintendoSwitchStructuralInspector,
    _parse_cnmt_xml,
    inspect_switch_package,
)


def _pfs0(
    entries: tuple[
        tuple[str, bytes],
        ...,
    ],
) -> bytes:
    strings = bytearray()
    records = bytearray()
    payload = bytearray()

    for name, data in entries:
        name_offset = len(strings)

        strings.extend(
            name.encode("utf-8")
            + b"\x00"
        )

        records.extend(
            len(payload).to_bytes(
                8,
                "little",
            )
        )
        records.extend(
            len(data).to_bytes(
                8,
                "little",
            )
        )
        records.extend(
            name_offset.to_bytes(
                4,
                "little",
            )
        )
        records.extend(
            bytes(4)
        )

        payload.extend(data)

    return bytes(
        b"PFS0"
        + len(entries).to_bytes(
            4,
            "little",
        )
        + len(strings).to_bytes(
            4,
            "little",
        )
        + bytes(4)
        + records
        + strings
        + payload
    )


def _hfs0(
    entries: tuple[
        tuple[str, bytes],
        ...,
    ],
) -> bytes:
    strings = bytearray()
    records = bytearray()
    payload = bytearray()

    for name, data in entries:
        name_offset = len(strings)

        strings.extend(
            name.encode("utf-8")
            + b"\x00"
        )

        records.extend(
            len(payload).to_bytes(
                8,
                "little",
            )
        )
        records.extend(
            len(data).to_bytes(
                8,
                "little",
            )
        )
        records.extend(
            name_offset.to_bytes(
                4,
                "little",
            )
        )
        records.extend(
            len(data).to_bytes(
                4,
                "little",
            )
        )
        records.extend(
            bytes(8)
        )
        records.extend(
            bytes(32)
        )

        payload.extend(data)

    return bytes(
        b"HFS0"
        + len(entries).to_bytes(
            4,
            "little",
        )
        + len(strings).to_bytes(
            4,
            "little",
        )
        + bytes(4)
        + records
        + strings
        + payload
    )


def _application_xml(
    *,
    application_id: str = "0100123456789000",
    version: int = 0,
    patch_id: str = "0100123456789800",
) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<ContentMeta>"
        "<Type>Application</Type>"
        f"<Id>0x{application_id}</Id>"
        f"<Version>{version}</Version>"
        "<RequiredSystemVersion>123456</RequiredSystemVersion>"
        "<Content>"
        "<Type>Program</Type>"
        "<Id>00112233445566778899aabbccddeeff</Id>"
        "</Content>"
        f"<PatchId>0x{patch_id}</PatchId>"
        "</ContentMeta>"
    ).encode()


def _write_nsp(
    path: Path,
    *,
    include_xml: bool = True,
    include_ticket: bool = True,
) -> None:
    entries = [
        (
            "00112233445566778899aabbccddeeff.nca",
            b"encrypted-program",
        ),
        (
            "11223344556677889900aabbccddeeff.cnmt.nca",
            b"encrypted-meta",
        ),
    ]

    if include_xml:
        entries.append(
            (
                "11223344556677889900aabbccddeeff.cnmt.xml",
                _application_xml(),
            )
        )

    if include_ticket:
        entries.append(
            (
                "01001234567890000000000000000005.tik",
                b"ticket",
            )
        )

    path.write_bytes(
        _pfs0(
            tuple(entries)
        )
    )


def _write_xci(
    path: Path,
) -> None:
    secure = _hfs0(
        (
            (
                "00112233445566778899aabbccddeeff.nca",
                b"encrypted-program",
            ),
            (
                "11223344556677889900aabbccddeeff.cnmt.nca",
                b"encrypted-meta",
            ),
            (
                "01001234567898000000000000000005.tik",
                b"ticket",
            ),
        )
    )

    root = _hfs0(
        (
            (
                "secure",
                secure,
            ),
        )
    )

    header = bytearray(
        0x200
    )

    header[
        0x100:0x104
    ] = b"HEAD"

    header[
        0x130:0x138
    ] = (
        0x200
    ).to_bytes(
        8,
        "little",
    )

    path.write_bytes(
        bytes(header)
        + root
    )


def test_parse_application_cnmt_xml() -> None:
    metadata = _parse_cnmt_xml(
        _application_xml(
            application_id=(
                "0100123456789000"
            ),
            version=7,
            patch_id=(
                "0100123456789800"
            ),
        )
    )

    assert metadata is not None
    assert (
        metadata.application_id
        == "0100123456789000"
    )
    assert metadata.version == 7
    assert (
        metadata.required_system_version
        == 123456
    )
    assert (
        metadata.patch_id
        == "0100123456789800"
    )


def test_non_application_cnmt_xml_is_not_application() -> None:
    data = (
        b"<ContentMeta>"
        b"<Type>Patch</Type>"
        b"<Id>0x0100123456789800</Id>"
        b"<Version>1</Version>"
        b"</ContentMeta>"
    )

    assert _parse_cnmt_xml(
        data
    ) is None


def test_inspect_nsp_with_application_xml(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"
    _write_nsp(path)

    metadata = inspect_switch_package(
        path
    )

    assert (
        metadata.representation
        == "package"
    )
    assert (
        metadata.container_format
        == "pfs0"
    )
    assert metadata.nca_count == 2
    assert metadata.cnmt_nca_count == 1

    assert metadata.application is not None
    assert (
        metadata.application.application_id
        == "0100123456789000"
    )

    assert len(metadata.rights) == 1
    assert (
        metadata.rights[0].rights_title_id
        == "0100123456789000"
    )


def test_inspect_nsp_without_xml_still_detects(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"

    _write_nsp(
        path,
        include_xml=False,
    )

    metadata = inspect_switch_package(
        path
    )

    assert metadata.application is None
    assert metadata.cnmt_nca_count == 1


def test_inspect_xci_preserves_rights_without_application_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.xci"
    _write_xci(path)

    metadata = inspect_switch_package(
        path
    )

    assert (
        metadata.representation
        == "game-card-image"
    )
    assert (
        metadata.container_format
        == "xci"
    )
    assert metadata.application is None

    assert len(metadata.rights) == 1
    assert (
        metadata.rights[0].rights_title_id
        == "0100123456789800"
    )


def test_detector_identifies_nsp(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"
    _write_nsp(path)

    detection = (
        NintendoSwitchPlatformDetector()
        .detect(path)
    )

    assert detection.best is not None
    assert (
        detection.best.platform
        == "nintendo-switch"
    )
    assert (
        detection.best.confidence
        == 100
    )
    assert (
        detection.best.evidence[0].value
        == "0100123456789000"
    )


def test_detector_identifies_xci(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.xci"
    _write_xci(path)

    detection = (
        NintendoSwitchPlatformDetector()
        .detect(path)
    )

    assert detection.best is not None
    assert (
        detection.best.platform
        == "nintendo-switch"
    )
    assert (
        detection.best.evidence[0].value
        == "xci"
    )


def test_inspector_preserves_nsp_application_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"
    _write_nsp(path)

    result = (
        NintendoSwitchStructuralInspector()
        .inspect(path)
    )

    assert result is not None

    representation = (
        result.physical_representation
    )

    assert (
        representation.kind
        == "package"
    )
    assert (
        representation.format
        == "pfs0"
    )

    local = result.local_metadata

    assert local is not None
    assert (
        local.platform
        == "nintendo-switch"
    )

    values = {
        (
            item.namespace,
            item.value,
        )
        for item in local.identifiers
    }

    assert (
        "switch-application-id",
        "0100123456789000",
    ) in values

    assert (
        "switch-rights-title-id",
        "0100123456789000",
    ) in values

    assert (
        local.software_versions[0].value
        == "0"
    )

    assert (
        local.native_metadata["patch_id"]
        == "0100123456789800"
    )


def test_inspector_does_not_promote_xci_ticket_to_application_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.xci"
    _write_xci(path)

    result = (
        NintendoSwitchStructuralInspector()
        .inspect(path)
    )

    assert result is not None
    assert result.local_metadata is not None

    namespaces = {
        item.namespace
        for item
        in result.local_metadata.identifiers
    }

    assert (
        "switch-application-id"
        not in namespaces
    )

    assert (
        "switch-rights-title-id"
        in namespaces
    )


def test_plain_pfs0_is_not_switch(
    tmp_path: Path,
) -> None:
    path = tmp_path / "generic.pfs0"

    path.write_bytes(
        _pfs0(
            (
                (
                    "readme.txt",
                    b"hello",
                ),
            )
        )
    )

    detection = (
        NintendoSwitchPlatformDetector()
        .detect(path)
    )

    assert detection.best is None

    assert (
        NintendoSwitchStructuralInspector()
        .inspect(path)
        is None
    )


def test_nsp_requires_cnmt_nca(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.nsp"

    path.write_bytes(
        _pfs0(
            (
                (
                    "00112233445566778899aabbccddeeff.nca",
                    b"program",
                ),
            )
        )
    )

    with pytest.raises(
        NintendoSwitchFormatError,
        match="NCA/CNMT",
    ):
        inspect_switch_package(path)


def test_invalid_cnmt_xml_is_rejected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.nsp"

    path.write_bytes(
        _pfs0(
            (
                (
                    "00112233445566778899aabbccddeeff.nca",
                    b"program",
                ),
                (
                    "11223344556677889900aabbccddeeff.cnmt.nca",
                    b"meta",
                ),
                (
                    "11223344556677889900aabbccddeeff.cnmt.xml",
                    b"<ContentMeta>",
                ),
            )
        )
    )

    with pytest.raises(
        NintendoSwitchFormatError,
        match="valid XML",
    ):
        inspect_switch_package(path)


def test_nested_content_id_does_not_replace_application_id() -> None:
    data = (
        b"<ContentMeta>"
        b"<Type>Application</Type>"
        b"<Id>0x0100123456789000</Id>"
        b"<Version>0</Version>"
        b"<Content>"
        b"<Type>Program</Type>"
        b"<Id>AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA</Id>"
        b"</Content>"
        b"</ContentMeta>"
    )

    metadata = _parse_cnmt_xml(
        data
    )

    assert metadata is not None
    assert (
        metadata.application_id
        == "0100123456789000"
    )


def test_detector_rejects_missing_file(
    tmp_path: Path,
) -> None:
    detection = (
        NintendoSwitchPlatformDetector()
        .detect(
            tmp_path / "missing.bin"
        )
    )

    assert detection.best is None


def test_inspector_rejects_missing_file(
    tmp_path: Path,
) -> None:
    assert (
        NintendoSwitchStructuralInspector()
        .inspect(
            tmp_path / "missing.bin"
        )
        is None
    )


def test_cnmt_rejects_non_contentmeta_root() -> None:
    with pytest.raises(
        NintendoSwitchFormatError,
        match="root is not ContentMeta",
    ):
        _parse_cnmt_xml(
            b"<Other><Type>Application</Type></Other>"
        )


def test_cnmt_rejects_duplicate_root_type() -> None:
    with pytest.raises(
        NintendoSwitchFormatError,
        match="duplicate root Type",
    ):
        _parse_cnmt_xml(
            b"<ContentMeta>"
            b"<Type>Application</Type>"
            b"<Type>Application</Type>"
            b"</ContentMeta>"
        )


def test_application_cnmt_requires_root_id() -> None:
    with pytest.raises(
        NintendoSwitchFormatError,
        match="missing root Id",
    ):
        _parse_cnmt_xml(
            b"<ContentMeta>"
            b"<Type>Application</Type>"
            b"<Version>0</Version>"
            b"</ContentMeta>"
        )


def test_application_cnmt_requires_version() -> None:
    with pytest.raises(
        NintendoSwitchFormatError,
        match="missing Version",
    ):
        _parse_cnmt_xml(
            b"<ContentMeta>"
            b"<Type>Application</Type>"
            b"<Id>0x0100123456789000</Id>"
            b"</ContentMeta>"
        )


def test_application_cnmt_rejects_invalid_id() -> None:
    with pytest.raises(
        NintendoSwitchFormatError,
        match="application ID",
    ):
        _parse_cnmt_xml(
            b"<ContentMeta>"
            b"<Type>Application</Type>"
            b"<Id>0xNOTHEX</Id>"
            b"<Version>0</Version>"
            b"</ContentMeta>"
        )


def test_application_cnmt_rejects_invalid_version() -> None:
    with pytest.raises(
        NintendoSwitchFormatError,
        match="application version is not an integer",
    ):
        _parse_cnmt_xml(
            b"<ContentMeta>"
            b"<Type>Application</Type>"
            b"<Id>0x0100123456789000</Id>"
            b"<Version>invalid</Version>"
            b"</ContentMeta>"
        )


def test_application_cnmt_rejects_negative_version() -> None:
    with pytest.raises(
        NintendoSwitchFormatError,
        match="must not be negative",
    ):
        _parse_cnmt_xml(
            b"<ContentMeta>"
            b"<Type>Application</Type>"
            b"<Id>0x0100123456789000</Id>"
            b"<Version>-1</Version>"
            b"</ContentMeta>"
        )


def test_application_cnmt_rejects_invalid_patch_id() -> None:
    with pytest.raises(
        NintendoSwitchFormatError,
        match="patch ID",
    ):
        _parse_cnmt_xml(
            b"<ContentMeta>"
            b"<Type>Application</Type>"
            b"<Id>0x0100123456789000</Id>"
            b"<Version>0</Version>"
            b"<PatchId>invalid</PatchId>"
            b"</ContentMeta>"
        )


def test_ticket_metadata_ignores_non_hex_ticket(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"

    path.write_bytes(
        _pfs0(
            (
                (
                    "00112233445566778899aabbccddeeff.nca",
                    b"program",
                ),
                (
                    "11223344556677889900aabbccddeeff.cnmt.nca",
                    b"meta",
                ),
                (
                    "not-a-rights-id.tik",
                    b"ticket",
                ),
            )
        )
    )

    metadata = inspect_switch_package(path)

    assert metadata.rights == ()
