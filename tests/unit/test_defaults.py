from pathlib import Path

from rom_metadata_framework.defaults import (
    build_default_normalizer,
)
from rom_metadata_framework.dolphin import DolphinAdapter
from rom_metadata_framework.nes import NesAdapter


def test_default_normalizer_registers_nes_then_dolphin() -> None:
    router = build_default_normalizer()

    assert len(router.normalizers) == 2

    nes, dolphin = router.normalizers

    assert isinstance(nes, NesAdapter)
    assert isinstance(dolphin, DolphinAdapter)

    assert nes.name == "nes"
    assert dolphin.name == "dolphin"


def test_default_normalizer_keeps_headerless_nes_disabled() -> None:
    router = build_default_normalizer()

    nes = router.normalizers[0]

    assert isinstance(nes, NesAdapter)
    assert not nes.allow_headerless


def test_default_normalizer_can_enable_headerless_nes() -> None:
    router = build_default_normalizer(
        allow_headerless_nes=True,
    )

    nes = router.normalizers[0]

    assert isinstance(nes, NesAdapter)
    assert nes.allow_headerless


def test_default_normalizer_passes_dolphin_runtime_configuration(
    tmp_path: Path,
) -> None:
    executable = "/example/dolphin-tool"

    router = build_default_normalizer(
        dolphin_executable=executable,
        dolphin_temporary_directory=tmp_path,
    )

    dolphin = router.normalizers[1]

    assert isinstance(dolphin, DolphinAdapter)
    assert dolphin.backend.executable == executable
    assert dolphin.temporary_directory == tmp_path


def test_default_router_routes_headered_nes_without_opt_in(
    tmp_path: Path,
) -> None:
    header = bytearray(16)
    header[:4] = b"NES\x1a"
    header[4] = 1

    path = tmp_path / "headered.bin"
    path.write_bytes(
        bytes(header)
        + (b"P" * (16 * 1024))
    )

    router = build_default_normalizer(
        dolphin_executable="/definitely/missing/dolphin-tool",
    )

    matches = router.supporting_normalizers(path)

    assert tuple(
        normalizer.name
        for normalizer in matches
    ) == ("nes",)


def test_default_router_does_not_route_headerless_nes_without_opt_in(
    tmp_path: Path,
) -> None:
    path = tmp_path / "headerless.nes"
    path.write_bytes(b"headerless-content")

    router = build_default_normalizer(
        dolphin_executable="/definitely/missing/dolphin-tool",
    )

    assert router.supporting_normalizers(path) == ()


def test_default_router_routes_headerless_nes_with_opt_in(
    tmp_path: Path,
) -> None:
    path = tmp_path / "headerless.nes"
    path.write_bytes(b"headerless-content")

    router = build_default_normalizer(
        allow_headerless_nes=True,
        dolphin_executable="/definitely/missing/dolphin-tool",
    )

    matches = router.supporting_normalizers(path)

    assert tuple(
        normalizer.name
        for normalizer in matches
    ) == ("nes",)
