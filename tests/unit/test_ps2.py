from __future__ import annotations

from pathlib import Path

import pytest

from rom_metadata_framework.detection import (
    PlatformDetector,
)
from rom_metadata_framework.ps2 import (
    ISO_PVD_OFFSET,
    ISO_SECTOR_SIZE,
    Ps2FormatError,
    Ps2PlatformDetector,
    inspect_ps2_iso,
)


def _both_endian_u32(value: int) -> bytes:
    return (
        value.to_bytes(4, "little")
        + value.to_bytes(4, "big")
    )


def _both_endian_u16(value: int) -> bytes:
    return (
        value.to_bytes(2, "little")
        + value.to_bytes(2, "big")
    )


def _directory_record(
    name: bytes,
    *,
    extent: int,
    size: int,
    directory: bool = False,
) -> bytes:
    name_length = len(name)

    record_length = (
        33
        + name_length
        + (1 if name_length % 2 == 0 else 0)
    )

    record = bytearray(record_length)

    record[0] = record_length
    record[1] = 0
    record[2:10] = _both_endian_u32(extent)
    record[10:18] = _both_endian_u32(size)

    record[18:25] = bytes(
        (
            126,
            8,
            23,
            12,
            0,
            0,
            0,
        )
    )

    record[25] = 0x02 if directory else 0x00
    record[26] = 0
    record[27] = 0
    record[28:32] = _both_endian_u16(1)
    record[32] = name_length
    record[33 : 33 + name_length] = name

    return bytes(record)


def _write_iso(
    path: Path,
    *,
    system_cnf: bytes | None,
    volume_identifier: str = "SLUS_20013",
) -> None:
    root_sector = 20
    system_sector = 21

    root_entries = [
        _directory_record(
            b"\x00",
            extent=root_sector,
            size=ISO_SECTOR_SIZE,
            directory=True,
        ),
        _directory_record(
            b"\x01",
            extent=root_sector,
            size=ISO_SECTOR_SIZE,
            directory=True,
        ),
    ]

    if system_cnf is not None:
        root_entries.append(
            _directory_record(
                b"SYSTEM.CNF;1",
                extent=system_sector,
                size=len(system_cnf),
            )
        )

    root_data = b"".join(root_entries)

    image_size = 22 * ISO_SECTOR_SIZE
    image = bytearray(image_size)

    pvd = bytearray(ISO_SECTOR_SIZE)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1

    encoded_volume = volume_identifier.encode("ascii")
    pvd[40:72] = encoded_volume.ljust(32, b" ")
    pvd[128:132] = _both_endian_u16(
        ISO_SECTOR_SIZE
    )

    root_record = _directory_record(
        b"\x00",
        extent=root_sector,
        size=ISO_SECTOR_SIZE,
        directory=True,
    )

    pvd[
        156 : 156 + len(root_record)
    ] = root_record

    image[
        ISO_PVD_OFFSET :
        ISO_PVD_OFFSET + ISO_SECTOR_SIZE
    ] = pvd

    root_offset = root_sector * ISO_SECTOR_SIZE
    image[
        root_offset : root_offset + len(root_data)
    ] = root_data

    if system_cnf is not None:
        system_offset = system_sector * ISO_SECTOR_SIZE
        image[
            system_offset :
            system_offset + len(system_cnf)
        ] = system_cnf

    path.write_bytes(image)


def test_inspect_ps2_iso_extracts_boot2_and_product_code(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\\\SLUS_200.13;1\r\n"
            b"VER = 1.00\r\n"
            b"VMODE = NTSC\r\n"
        ),
    )

    metadata = inspect_ps2_iso(path)

    assert metadata.volume_identifier == "SLUS_20013"
    assert metadata.boot_path == (
        r"cdrom0:\\SLUS_200.13;1"
    )
    assert metadata.product_code == "SLUS-20013"
    assert metadata.system_cnf_extent == 21


def test_ps2_detector_returns_canonical_platform(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.bin"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\\\SCUS_971.24;1\n"
        ),
        volume_identifier="PLAYSTATION",
    )

    detector = Ps2PlatformDetector()

    assert isinstance(
        detector,
        PlatformDetector,
    )

    detection = detector.detect(path)

    assert detection.best is not None
    assert detection.best.platform == "playstation-2"
    assert detection.best.confidence == 100

    evidence = detection.best.evidence[0]

    assert evidence.source == "ps2-system-cnf"
    assert evidence.method == "boot2"
    assert evidence.strength == 100
    assert (
        evidence.details["product_code"]
        == "SCUS-97124"
    )
    assert (
        evidence.details["volume_identifier"]
        == "PLAYSTATION"
    )


def test_ps2_detector_rejects_iso_without_system_cnf(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ordinary.iso"

    _write_iso(
        path,
        system_cnf=None,
        volume_identifier="ORDINARY_DISC",
    )

    detection = Ps2PlatformDetector().detect(path)

    assert detection.candidates == ()
    assert detection.best is None


def test_ps2_detector_rejects_system_cnf_without_boot2(
    tmp_path: Path,
) -> None:
    path = tmp_path / "not-ps2.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT = cdrom:\\\\SLUS_000.00;1\n"
        ),
    )

    detection = Ps2PlatformDetector().detect(path)

    assert detection.candidates == ()


def test_inspect_ps2_iso_rejects_non_iso(
    tmp_path: Path,
) -> None:
    path = tmp_path / "random.bin"
    path.write_bytes(b"not an iso")

    with pytest.raises(
        Ps2FormatError,
        match="primary volume descriptor",
    ):
        inspect_ps2_iso(path)


def test_product_code_can_be_absent_without_losing_ps2_detection(
    tmp_path: Path,
) -> None:
    path = tmp_path / "homebrew.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\\\BOOT.ELF;1\n"
        ),
    )

    metadata = inspect_ps2_iso(path)

    assert metadata.product_code is None

    detection = Ps2PlatformDetector().detect(path)

    assert detection.best is not None
    assert detection.best.platform == "playstation-2"
    assert "product_code" not in (
        detection.best.evidence[0].details
    )


def test_inspect_ps2_iso_rejects_mismatched_endian_root_extent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad-endian.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\SLUS_200.13;1\n"
        ),
    )

    image = bytearray(path.read_bytes())

    root_extent_offset = (
        ISO_PVD_OFFSET + 156 + 2
    )

    image[
        root_extent_offset + 4 :
        root_extent_offset + 8
    ] = (999).to_bytes(4, "big")

    path.write_bytes(image)

    with pytest.raises(
        Ps2FormatError,
        match="endian values disagree",
    ):
        inspect_ps2_iso(path)


def test_inspect_ps2_iso_rejects_root_extent_beyond_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad-root-extent.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\SLUS_200.13;1\n"
        ),
    )

    image = bytearray(path.read_bytes())

    root_extent_offset = (
        ISO_PVD_OFFSET + 156 + 2
    )
    impossible_extent = 1000

    image[
        root_extent_offset :
        root_extent_offset + 8
    ] = _both_endian_u32(
        impossible_extent
    )

    path.write_bytes(image)

    with pytest.raises(
        Ps2FormatError,
        match="root directory extent lies beyond",
    ):
        inspect_ps2_iso(path)


def test_inspect_ps2_iso_rejects_nonstandard_block_size(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad-block-size.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\SLUS_200.13;1\n"
        ),
    )

    image = bytearray(path.read_bytes())

    block_size_offset = ISO_PVD_OFFSET + 128

    image[
        block_size_offset :
        block_size_offset + 4
    ] = _both_endian_u16(1024)

    path.write_bytes(image)

    with pytest.raises(
        Ps2FormatError,
        match="logical block size is not 2048",
    ):
        inspect_ps2_iso(path)


def test_ps2_structural_inspector_returns_representation_and_metadata(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.ps2 import Ps2StructuralInspector

    path = tmp_path / "game.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\SLUS_200.13;1\n"
        ),
    )

    result = Ps2StructuralInspector().inspect(path)

    assert result is not None

    representation = result.physical_representation

    assert representation is not None
    assert representation.kind == "disc-image"
    assert representation.format == "iso9660"
    assert representation.metadata == {
        "volume_identifier": "SLUS_20013",
    }

    metadata = result.local_metadata

    assert metadata is not None
    assert metadata.platform == "playstation-2"
    assert len(metadata.identifiers) == 1
    assert metadata.identifiers[0].namespace == (
        "ps2-product-code"
    )
    assert metadata.identifiers[0].value == "SLUS-20013"
    assert metadata.boot["path"] == (
        r"cdrom0:\SLUS_200.13;1"
    )
    assert metadata.native_metadata[
        "volume_identifier"
    ] == "SLUS_20013"


def test_ps2_structural_inspector_preserves_homebrew_without_serial(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.ps2 import Ps2StructuralInspector

    path = tmp_path / "homebrew.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\BOOT.ELF;1\n"
        ),
    )

    result = Ps2StructuralInspector().inspect(path)

    assert result is not None
    assert result.local_metadata is not None
    assert result.local_metadata.identifiers == ()
    assert result.local_metadata.boot["path"] == (
        r"cdrom0:\BOOT.ELF;1"
    )


def test_ps2_structural_inspector_returns_none_for_unsupported_file(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.ps2 import Ps2StructuralInspector

    path = tmp_path / "ordinary.bin"
    path.write_bytes(b"ordinary")

    assert Ps2StructuralInspector().inspect(path) is None


def test_ps2_structural_inspector_integrates_with_identify_file(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.defaults import (
        build_default_detector,
        build_default_inspector,
    )
    from rom_metadata_framework.identification import (
        identify_file,
    )

    path = tmp_path / "game.iso"

    _write_iso(
        path,
        system_cnf=(
            b"BOOT2 = cdrom0:\\SLUS_200.13;1\n"
        ),
    )

    class Resolver:
        def __init__(self) -> None:
            self.physical_calls = 0
            self.normalized_lookup_calls = 0

        def identify(self, identity):
            self.physical_calls += 1

        def identify_lookup(self, lookup):
            self.normalized_lookup_calls += 1

    resolver = Resolver()

    result = identify_file(
        path,
        detector=build_default_detector(),
        resolver=resolver,
        inspector=build_default_inspector(),
    )

    assert result.platform_detection.best is not None
    assert (
        result.platform_detection.best.platform
        == "playstation-2"
    )

    assert result.physical_representation is not None
    assert result.physical_representation.kind == "disc-image"
    assert result.physical_representation.format == "iso9660"
    assert result.physical_representation.metadata == {
        "volume_identifier": "SLUS_20013",
    }

    assert result.local_metadata is not None
    assert result.local_metadata.platform == "playstation-2"
    assert len(result.local_metadata.identifiers) == 1
    assert (
        result.local_metadata.identifiers[0].namespace
        == "ps2-product-code"
    )
    assert (
        result.local_metadata.identifiers[0].value
        == "SLUS-20013"
    )
    assert result.local_metadata.boot["path"] == (
        r"cdrom0:\SLUS_200.13;1"
    )

    assert result.normalized_content is None
    assert result.normalized_match is None

    assert resolver.physical_calls == 1
    assert resolver.normalized_lookup_calls == 0
