from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from rom_metadata_framework.defaults import (
    DEFAULT_RUNTIME_CONFIG,
    DefaultRuntimeConfig,
    build_default_normalizer,
)
from rom_metadata_framework.dolphin import DolphinAdapter
from rom_metadata_framework.nes import NesAdapter
from rom_metadata_framework.xbox import XboxAdapter


def test_default_normalizer_registers_nes_dolphin_xbox() -> None:
    router = build_default_normalizer()

    assert len(router.normalizers) == 3

    nes, dolphin, xbox = router.normalizers

    assert isinstance(nes, NesAdapter)
    assert isinstance(dolphin, DolphinAdapter)
    assert isinstance(xbox, XboxAdapter)

    assert nes.name == "nes"
    assert dolphin.name == "dolphin"
    assert xbox.name == "xbox"


def test_default_normalizer_keeps_headerless_nes_disabled() -> None:
    router = build_default_normalizer()

    nes = router.normalizers[0]

    assert isinstance(nes, NesAdapter)
    assert not nes.allow_headerless


def test_default_normalizer_can_enable_headerless_nes() -> None:
    router = build_default_normalizer(
        DefaultRuntimeConfig(
            allow_headerless_nes=True,
        )
    )

    nes = router.normalizers[0]

    assert isinstance(nes, NesAdapter)
    assert nes.allow_headerless


def test_default_normalizer_passes_dolphin_runtime_configuration(
    tmp_path: Path,
) -> None:
    executable = "/example/dolphin-tool"

    router = build_default_normalizer(
        DefaultRuntimeConfig(
            dolphin_executable=executable,
            dolphin_temporary_directory=tmp_path,
        )
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
    path.write_bytes(bytes(header) + (b"P" * (16 * 1024)))

    router = build_default_normalizer(
        DefaultRuntimeConfig(
            dolphin_executable="/definitely/missing/dolphin-tool",
            xbox_executable="/definitely/missing/xdvdfs",
        )
    )

    matches = router.supporting_normalizers(path)

    assert tuple(normalizer.name for normalizer in matches) == ("nes",)


def test_default_router_does_not_route_headerless_nes_without_opt_in(
    tmp_path: Path,
) -> None:
    path = tmp_path / "headerless.nes"
    path.write_bytes(b"headerless-content")

    router = build_default_normalizer(
        DefaultRuntimeConfig(
            dolphin_executable="/definitely/missing/dolphin-tool",
            xbox_executable="/definitely/missing/xdvdfs",
        )
    )

    assert router.supporting_normalizers(path) == ()


def test_default_router_routes_headerless_nes_with_opt_in(
    tmp_path: Path,
) -> None:
    path = tmp_path / "headerless.nes"
    path.write_bytes(b"headerless-content")

    router = build_default_normalizer(
        DefaultRuntimeConfig(
            allow_headerless_nes=True,
            dolphin_executable="/definitely/missing/dolphin-tool",
            xbox_executable="/definitely/missing/xdvdfs",
        )
    )

    matches = router.supporting_normalizers(path)

    assert tuple(normalizer.name for normalizer in matches) == ("nes",)


def test_default_normalizer_passes_xbox_runtime_configuration(
    tmp_path: Path,
) -> None:
    executable = "/example/xdvdfs"

    router = build_default_normalizer(
        DefaultRuntimeConfig(
            xbox_executable=executable,
            xbox_temporary_directory=tmp_path,
        )
    )

    xbox = router.normalizers[2]

    assert isinstance(xbox, XboxAdapter)
    assert xbox.backend.executable == executable
    assert xbox.temporary_directory == tmp_path


def test_missing_external_adapters_do_not_block_supported_nes(
    tmp_path: Path,
) -> None:
    header = bytearray(16)
    header[:4] = b"NES\x1a"
    header[4] = 1

    path = tmp_path / "game.bin"
    path.write_bytes(bytes(header) + (b"P" * (16 * 1024)))

    router = build_default_normalizer(
        DefaultRuntimeConfig(
            dolphin_executable="/definitely/missing/dolphin-tool",
            xbox_executable="/definitely/missing/xdvdfs",
        )
    )

    probes = {probe.normalizer: probe for _, probe in router.probe_normalizers(path)}

    assert probes["nes"].supported
    assert probes["dolphin"].terminal_failure
    assert probes["xbox"].terminal_failure

    assert router.select(path).name == "nes"


def test_default_runtime_config_matches_framework_defaults() -> None:
    assert DEFAULT_RUNTIME_CONFIG == DefaultRuntimeConfig()
    assert not DEFAULT_RUNTIME_CONFIG.allow_headerless_nes


def test_default_runtime_config_normalizes_values(
    tmp_path: Path,
) -> None:
    config = DefaultRuntimeConfig(
        dolphin_executable="  dolphin-custom  ",
        dolphin_temporary_directory=tmp_path,
        xbox_executable="  xdvdfs-custom  ",
        xbox_temporary_directory=tmp_path,
    )

    assert config.dolphin_executable == "dolphin-custom"
    assert config.dolphin_temporary_directory == tmp_path
    assert config.xbox_executable == "xdvdfs-custom"
    assert config.xbox_temporary_directory == tmp_path


def test_default_runtime_config_is_frozen() -> None:
    config = DefaultRuntimeConfig()

    with pytest.raises(FrozenInstanceError):
        config.allow_headerless_nes = True


@pytest.mark.parametrize(
    "field",
    (
        "dolphin_executable",
        "xbox_executable",
    ),
)
def test_default_runtime_config_rejects_empty_executable(
    field: str,
) -> None:
    with pytest.raises(ValueError):
        DefaultRuntimeConfig(**{field: " "})


def test_default_normalizer_rejects_invalid_config() -> None:
    with pytest.raises(
        TypeError,
        match="DefaultRuntimeConfig",
    ):
        build_default_normalizer(None)


def test_default_detector_registers_nes_ps2_dolphin_xbox() -> None:
    from rom_metadata_framework.defaults import build_default_detector
    from rom_metadata_framework.dolphin import DolphinPlatformDetector
    from rom_metadata_framework.nes import NesPlatformDetector
    from rom_metadata_framework.ps2 import Ps2PlatformDetector
    from rom_metadata_framework.xbox import XboxPlatformDetector

    detector = build_default_detector()

    assert len(detector.detectors) == 4
    nes, ps2, dolphin, xbox = detector.detectors
    assert isinstance(nes, NesPlatformDetector)
    assert isinstance(ps2, Ps2PlatformDetector)
    assert isinstance(dolphin, DolphinPlatformDetector)
    assert isinstance(xbox, XboxPlatformDetector)


def test_default_detector_passes_backend_configuration() -> None:
    from rom_metadata_framework.defaults import (
        DefaultRuntimeConfig,
        build_default_detector,
    )
    from rom_metadata_framework.dolphin import DolphinPlatformDetector
    from rom_metadata_framework.xbox import XboxPlatformDetector

    detector = build_default_detector(
        DefaultRuntimeConfig(
            dolphin_executable="/example/dolphin-tool",
            xbox_executable="/example/xdvdfs",
        )
    )

    dolphin = detector.detectors[2]
    xbox = detector.detectors[3]

    assert isinstance(dolphin, DolphinPlatformDetector)
    assert isinstance(xbox, XboxPlatformDetector)
    assert dolphin.adapter.backend.executable == "/example/dolphin-tool"
    assert xbox.adapter.backend.executable == "/example/xdvdfs"


def test_default_detector_rejects_invalid_config() -> None:
    from rom_metadata_framework.defaults import build_default_detector

    with pytest.raises(TypeError, match="DefaultRuntimeConfig"):
        build_default_detector(None)


def test_default_inspector_registers_ps2() -> None:
    from rom_metadata_framework.defaults import (
        build_default_inspector,
    )
    from rom_metadata_framework.ps2 import (
        Ps2StructuralInspector,
    )

    inspector = build_default_inspector()

    assert len(inspector.inspectors) == 1
    assert isinstance(
        inspector.inspectors[0],
        Ps2StructuralInspector,
    )


def test_default_inspector_rejects_invalid_config() -> None:
    from rom_metadata_framework.defaults import (
        build_default_inspector,
    )

    with pytest.raises(
        TypeError,
        match="DefaultRuntimeConfig",
    ):
        build_default_inspector(None)
