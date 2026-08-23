from pathlib import Path

import pytest

from rom_metadata_framework.nes import (
    NES_MAGIC,
    NES_TRAINER_SIZE,
    NesAdapter,
    NesFormatError,
)


def make_header(
    *,
    prg_units: int = 1,
    chr_units: int = 1,
    nes2: bool = True,
    mapper: int = 0,
    submapper: int = 0,
    trainer: bool = False,
    horizontal_layout: bool = False,
    battery: bool = False,
    four_screen: bool = False,
    console_type: int = 0,
    prg_ram_shift: int = 0,
    prg_nvram_shift: int = 0,
    chr_ram_shift: int = 0,
    chr_nvram_shift: int = 0,
    timing_mode: int = 0,
    byte13: int = 0,
    misc_rom_count: int = 0,
    expansion_device: int = 0,
) -> bytes:
    header = bytearray(16)
    header[:4] = NES_MAGIC

    header[4] = prg_units & 0xFF
    header[5] = chr_units & 0xFF

    header[6] = (
        ((mapper & 0x0F) << 4)
        | (0x01 if horizontal_layout else 0)
        | (0x02 if battery else 0)
        | (0x04 if trainer else 0)
        | (0x08 if four_screen else 0)
    )

    header[7] = (mapper & 0xF0) | (console_type & 0x03)

    if nes2:
        header[7] |= 0x08
        header[8] = ((submapper & 0x0F) << 4) | ((mapper >> 8) & 0x0F)
        header[9] = (((chr_units >> 8) & 0x0F) << 4) | ((prg_units >> 8) & 0x0F)

        header[10] = ((prg_nvram_shift & 0x0F) << 4) | (prg_ram_shift & 0x0F)

        header[11] = ((chr_nvram_shift & 0x0F) << 4) | (chr_ram_shift & 0x0F)

        header[12] = timing_mode & 0x03
        header[13] = byte13 & 0xFF
        header[14] = misc_rom_count & 0x03
        header[15] = expansion_device & 0x3F

    return bytes(header)


def test_nes2_normalizes_prg_and_chr(
    tmp_path: Path,
) -> None:
    prg = b"P" * (16 * 1024)
    chr_data = b"C" * (8 * 1024)

    image = tmp_path / "example.nes"
    image.write_bytes(
        make_header(
            mapper=4,
            submapper=2,
        )
        + prg
        + chr_data
    )

    headerless = tmp_path / "example.unh"
    headerless.write_bytes(prg + chr_data)

    headered_identity = NesAdapter().identify(image)
    headerless_identity = NesAdapter(
        allow_headerless=True,
    ).identify(headerless)

    assert headered_identity.representation == "nes2"
    assert headered_identity.content.hashes == headerless_identity.content.hashes
    assert headered_identity.content.metadata["normalization"] == "prg+chr"
    assert headered_identity.header_metadata["mapper"] == "4"
    assert headered_identity.header_metadata["submapper"] == "2"


def test_ines_is_supported(
    tmp_path: Path,
) -> None:
    image = tmp_path / "example.nes"

    image.write_bytes(
        make_header(
            nes2=False,
        )
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
    )

    identity = NesAdapter().identify(image)

    assert identity.representation == "ines"
    assert identity.content.kind == "cartridge"


def test_headerless_requires_explicit_opt_in(
    tmp_path: Path,
) -> None:
    image = tmp_path / "example.nes"
    image.write_bytes(b"headerless-data")

    assert NesAdapter().supports(image) is False

    with pytest.raises(NesFormatError):
        NesAdapter().identify(image)

    assert (
        NesAdapter(
            allow_headerless=True,
        ).supports(image)
        is True
    )


def test_trainer_is_rejected_for_now(
    tmp_path: Path,
) -> None:
    image = tmp_path / "trainer.nes"

    image.write_bytes(
        make_header(
            trainer=True,
        )
        + (b"T" * 512)
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
    )

    with pytest.raises(
        NesFormatError,
        match="trainer",
    ):
        NesAdapter().identify(image)


def test_truncated_rom_is_rejected(
    tmp_path: Path,
) -> None:
    image = tmp_path / "short.nes"

    image.write_bytes(make_header() + b"too-short")

    with pytest.raises(
        NesFormatError,
        match="truncated",
    ):
        NesAdapter().identify(image)


def test_trailing_data_is_rejected(
    tmp_path: Path,
) -> None:
    image = tmp_path / "trailing.nes"

    image.write_bytes(
        make_header() + (b"P" * (16 * 1024)) + (b"C" * (8 * 1024)) + b"extra"
    )

    with pytest.raises(
        NesFormatError,
        match="trailing",
    ):
        NesAdapter().identify(image)


def test_nes2_exponent_multiplier_size(
    tmp_path: Path,
) -> None:
    header = bytearray(
        make_header(
            prg_units=0,
            chr_units=0,
        )
    )

    # NES 2.0 exponent/multiplier encoding:
    # 2^14 * 1 = 16 KiB PRG-ROM.
    header[4] = 14 << 2
    header[9] = (header[9] & 0xF0) | 0x0F

    prg = b"P" * (16 * 1024)

    image = tmp_path / "exponent.nes"
    image.write_bytes(bytes(header) + prg)

    identity = NesAdapter().identify(image)

    assert identity.content.metadata["prg_rom_size"] == str(16 * 1024)
    assert identity.content.metadata["chr_rom_size"] == "0"


def test_nes_platform_detector_detects_nes2(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.detection import (
        PlatformDetector,
    )
    from rom_metadata_framework.nes import (
        NesPlatformDetector,
    )

    image = tmp_path / "example.nes"
    image.write_bytes(make_header() + (b"P" * (16 * 1024)) + (b"C" * (8 * 1024)))

    detector = NesPlatformDetector()

    assert isinstance(
        detector,
        PlatformDetector,
    )

    detection = detector.detect(image)

    assert detection.best is not None
    assert detection.best.platform == "nes"
    assert detection.best.confidence == 100

    evidence = detection.best.evidence[0]

    assert evidence.source == "nes-header"
    assert evidence.method == "format-signature"
    assert evidence.details["representation"] == "nes2"


def test_nes_platform_detector_detects_ines(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.nes import (
        NesPlatformDetector,
    )

    image = tmp_path / "example.nes"
    image.write_bytes(
        make_header(
            nes2=False,
        )
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
    )

    detection = NesPlatformDetector().detect(image)

    assert detection.best is not None
    assert detection.best.platform == "nes"
    assert detection.best.evidence[0].details["representation"] == "ines"


def test_nes_platform_detector_does_not_guess_headerless(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.nes import (
        NesPlatformDetector,
    )

    image = tmp_path / "looks-like-nes.nes"
    image.write_bytes(b"headerless-content")

    detection = NesPlatformDetector().detect(image)

    assert detection.best is None
    assert detection.candidates == ()


def test_nes_normalized_content_includes_sha256(tmp_path: Path) -> None:
    import hashlib

    payload = b"\x12\x34\x56\x78" * (16 * 1024 // 4)

    header = bytearray(16)
    header[:4] = b"NES\x1a"
    header[4] = 1
    header[5] = 0

    path = tmp_path / "sha256-test.nes"
    path.write_bytes(bytes(header) + payload)

    result = NesAdapter().identify(path)

    assert result.content.hashes.sha256 == hashlib.sha256(payload).hexdigest()


def test_headerless_nes_support_requires_nes_extension(
    tmp_path: Path,
) -> None:
    payload = b"headerless-content"

    nes_path = tmp_path / "example.nes"
    nes_path.write_bytes(payload)

    binary_path = tmp_path / "example.bin"
    binary_path.write_bytes(payload)

    adapter = NesAdapter(
        allow_headerless=True,
    )

    assert adapter.supports(nes_path)
    assert not adapter.supports(binary_path)


def test_headered_nes_support_does_not_require_extension(
    tmp_path: Path,
) -> None:
    path = tmp_path / "example.bin"
    path.write_bytes(
        make_header(
            nes2=False,
        )
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
    )

    assert NesAdapter().supports(path)


def test_supports_rejects_truncated_headered_nes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "truncated.nes"

    path.write_bytes(
        make_header(
            nes2=False,
        )
        + (b"P" * ((16 * 1024) - 1))
        + (b"C" * (8 * 1024))
    )

    adapter = NesAdapter()

    assert not adapter.supports(path)

    with pytest.raises(NesFormatError):
        adapter.identify(path)


def test_supports_rejects_headered_nes_with_trailing_data(
    tmp_path: Path,
) -> None:
    path = tmp_path / "trailing.nes"

    path.write_bytes(
        make_header(
            nes2=False,
        )
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
        + b"extra"
    )

    adapter = NesAdapter()

    assert not adapter.supports(path)

    with pytest.raises(NesFormatError):
        adapter.identify(path)


def test_supports_rejects_trainer_bearing_nes(
    tmp_path: Path,
) -> None:
    header = bytearray(
        make_header(
            nes2=False,
        )
    )
    header[6] |= 0x04

    path = tmp_path / "trainer.nes"

    path.write_bytes(
        bytes(header)
        + (b"T" * NES_TRAINER_SIZE)
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
    )

    adapter = NesAdapter()

    assert not adapter.supports(path)

    with pytest.raises(NesFormatError):
        adapter.identify(path)


def test_supports_accepts_exact_nes2_exponent_size_image(
    tmp_path: Path,
) -> None:
    header = bytearray(16)
    header[:4] = NES_MAGIC
    header[4] = 14 << 2
    header[5] = 0
    header[7] = 0x08
    header[9] = 0x0F

    path = tmp_path / "exponent.nes"

    path.write_bytes(bytes(header) + (b"P" * (1 << 14)))

    adapter = NesAdapter()

    assert adapter.supports(path)

    result = adapter.identify(path)

    assert result.representation == "nes2"
    assert result.content.kind == "cartridge"


def test_probe_distinguishes_unrelated_from_unsafe_nes(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbeStatus,
    )

    unrelated = tmp_path / "unrelated.bin"
    unrelated.write_bytes(b"not-an-nes-image")

    header = make_header(
        nes2=False,
    )

    truncated = tmp_path / "truncated-probe.nes"
    truncated.write_bytes(header + (b"P" * ((16 * 1024) - 1)) + (b"C" * (8 * 1024)))

    appended = tmp_path / "appended-probe.nes"
    appended.write_bytes(header + (b"P" * (16 * 1024)) + (b"C" * (8 * 1024)) + b"extra")

    adapter = NesAdapter()

    assert adapter.probe(unrelated).status is NormalizerProbeStatus.UNSUPPORTED
    assert adapter.probe(truncated).status is NormalizerProbeStatus.UNSAFE
    assert adapter.probe(appended).status is NormalizerProbeStatus.UNSAFE


def test_probe_reports_supported_valid_nes(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbeStatus,
    )

    path = tmp_path / "valid-probe.nes"
    path.write_bytes(
        make_header(
            nes2=False,
        )
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
    )

    probe = NesAdapter().probe(path)

    assert probe.status is NormalizerProbeStatus.SUPPORTED
    assert probe.details["representation"] == "ines"
    assert probe.details["actual_size"] == (probe.details["expected_size"])


def test_probe_reports_trainer_nes_as_unsafe(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbeStatus,
    )

    header = bytearray(
        make_header(
            nes2=False,
        )
    )
    header[6] |= 0x04

    path = tmp_path / "trainer-probe.nes"
    path.write_bytes(
        bytes(header)
        + (b"T" * NES_TRAINER_SIZE)
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
    )

    probe = NesAdapter().probe(path)

    assert probe.status is NormalizerProbeStatus.UNSAFE
    assert probe.details["trainer"] == "true"


def test_probe_preserves_headerless_opt_in(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbeStatus,
    )

    path = tmp_path / "headerless.nes"
    path.write_bytes(b"headerless-content")

    default_probe = NesAdapter().probe(path)
    opt_in_probe = NesAdapter(
        allow_headerless=True,
    ).probe(path)

    assert default_probe.status is NormalizerProbeStatus.UNSUPPORTED
    assert opt_in_probe.status is NormalizerProbeStatus.SUPPORTED
    assert opt_in_probe.details["representation"] == "headerless"


def test_nes_runtime_capability_is_ready() -> None:
    from rom_metadata_framework.capability import RuntimeCapabilityStatus

    adapter = NesAdapter()
    capability = adapter.runtime_capability()

    assert capability.name == "nes-normalization"
    assert capability.status is RuntimeCapabilityStatus.READY
    assert capability.ready


def test_nes2_local_metadata_decodes_standard_header_fields(
    tmp_path: Path,
) -> None:
    image = tmp_path / "metadata.nes"

    image.write_bytes(
        make_header(
            mapper=4,
            submapper=2,
            horizontal_layout=True,
            battery=True,
            console_type=3,
            prg_ram_shift=7,
            prg_nvram_shift=6,
            chr_ram_shift=5,
            chr_nvram_shift=4,
            timing_mode=2,
            byte13=0x0A,
            expansion_device=0x12,
        )
        + (b"P" * (16 * 1024))
        + (b"C" * (8 * 1024))
    )

    identity = NesAdapter().identify(image)
    local = identity.local_metadata

    assert local.platform == "nes"

    assert local.hardware["mapper"] == "4"
    assert local.hardware["submapper"] == "2"

    assert local.hardware["nametable_layout"] == "horizontal"

    assert local.hardware["battery_or_nvram"] == "true"

    assert local.hardware["prg_ram_size"] == "8192"

    assert local.hardware["prg_nvram_size"] == "4096"

    assert local.hardware["chr_ram_size"] == "2048"

    assert local.hardware["chr_nvram_size"] == "1024"

    assert local.hardware["timing_mode"] == "multi-region"

    assert local.hardware["console_type"] == "extended"

    assert local.hardware["extended_console_type"] == "10"

    assert local.hardware["default_expansion_device"] == "18"


def test_ines_local_metadata_avoids_ambiguous_extended_bytes(
    tmp_path: Path,
) -> None:
    header = bytearray(
        make_header(
            nes2=False,
            mapper=1,
            battery=True,
        )
    )

    # Legacy iNES bytes 8-15 are historically ambiguous.
    header[8:16] = b"DISKDUDE"

    image = tmp_path / "legacy.nes"

    image.write_bytes(bytes(header) + (b"P" * (16 * 1024)) + (b"C" * (8 * 1024)))

    identity = NesAdapter().identify(image)
    local = identity.local_metadata

    assert local.hardware["mapper"] == "1"

    assert local.hardware["battery_or_nvram"] == "true"

    assert "timing_mode" not in local.hardware
    assert "prg_ram_size" not in local.hardware
    assert "default_expansion_device" not in local.hardware
