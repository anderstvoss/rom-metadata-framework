import json
from pathlib import Path

import pytest

from rom_metadata_framework.dolphin import (
    DolphinAdapter,
    DolphinResponseError,
)

GC_HEADER = {
    "block_size": 131072,
    "compression_level": 5,
    "compression_method": "Zstandard",
    "country": "USA",
    "game_id": "GALE01",
    "internal_name": "Super Smash Bros Melee",
    "region": "NTSC-U",
    "revision": 2,
}

WII_HEADER = {
    "block_size": 131072,
    "compression_level": 5,
    "compression_method": "Zstandard",
    "country": "USA",
    "game_id": "RMCE01",
    "internal_name": "MarioKartWii",
    "region": "NTSC-U",
    "revision": 0,
    "title_id": 281493537375045,
}

HASHES = {
    "crc32": "5365c84b",
    "md5": "0e63d4223b01d9aba596259dc155a174",
    "sha1": "d4e70c064cc714ba8400a849cf299dbd1aa326fc",
    "rchash": "326d2c2de5c8957637780da332ab9dbb",
}


def write_fake_dolphin(
    path: Path,
    *,
    header: dict[str, object],
    hashes: dict[str, str] | None = None,
) -> Path:
    hashes = hashes or HASHES

    path.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"header\" ]; then\n"
        f"  printf '%s\\n' '{json.dumps(header)}'\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = \"verify\" ]; then\n"
        "  while [ \"$#\" -gt 0 ]; do\n"
        "    if [ \"$1\" = \"-a\" ]; then\n"
        "      shift\n"
        "      case \"$1\" in\n"
        f"        crc32) printf '%s\\n' '{hashes['crc32']}' ;;\n"
        f"        md5) printf '%s\\n' '{hashes['md5']}' ;;\n"
        f"        sha1) printf '%s\\n' '{hashes['sha1']}' ;;\n"
        f"        rchash) printf '%s\\n' '{hashes['rchash']}' ;;\n"
        "        *) exit 3 ;;\n"
        "      esac\n"
        "      exit 0\n"
        "    fi\n"
        "    shift\n"
        "  done\n"
        "fi\n"
        "exit 2\n"
    )

    path.chmod(0o755)
    return path


def test_gamecube_disc_identity(tmp_path: Path) -> None:
    helper = write_fake_dolphin(
        tmp_path / "dolphin-tool",
        header=GC_HEADER,
    )

    image = tmp_path / "melee.rvz"
    image.write_bytes(b"synthetic-rvz")

    identity = DolphinAdapter(
        executable=str(helper),
    ).identify(image)

    assert identity.platform == "gamecube"
    assert identity.format == "rvz"
    assert identity.game_id == "GALE01"
    assert identity.revision == 2
    assert identity.region == "NTSC-U"
    assert identity.title_id is None
    assert identity.content.hashes.crc32 == HASHES["crc32"]
    assert identity.content.hashes.md5 == HASHES["md5"]
    assert identity.content.hashes.sha1 == HASHES["sha1"]
    assert (
        identity.content.specialized_identifiers[
            "retroachievements"
        ]
        == HASHES["rchash"]
    )
    assert identity.container_metadata["block_size"] == "131072"
    assert (
        identity.container_metadata["compression_method"]
        == "Zstandard"
    )


def test_wii_disc_identity(tmp_path: Path) -> None:
    hashes = dict(HASHES)
    hashes["rchash"] = "9ecf6959a4837316e1fceb90e84e5491"

    helper = write_fake_dolphin(
        tmp_path / "dolphin-tool",
        header=WII_HEADER,
        hashes=hashes,
    )

    image = tmp_path / "mario-kart.rvz"
    image.write_bytes(b"synthetic-rvz")

    identity = DolphinAdapter(
        executable=str(helper),
    ).identify(image)

    assert identity.platform == "wii"
    assert identity.game_id == "RMCE01"
    assert identity.revision == 0
    assert identity.title_id == "281493537375045"
    assert (
        identity.content.specialized_identifiers[
            "retroachievements"
        ]
        == hashes["rchash"]
    )


def test_legacy_zero_rchash_is_ignored(
    tmp_path: Path,
) -> None:
    hashes = dict(HASHES)
    hashes["rchash"] = "0"

    helper = write_fake_dolphin(
        tmp_path / "dolphin-tool",
        header=WII_HEADER,
        hashes=hashes,
    )

    image = tmp_path / "wii.rvz"
    image.write_bytes(b"synthetic-rvz")

    identity = DolphinAdapter(
        executable=str(helper),
    ).identify(image)

    assert "retroachievements" not in (
        identity.content.specialized_identifiers
    )


def test_invalid_regular_hash_is_rejected(
    tmp_path: Path,
) -> None:
    hashes = dict(HASHES)
    hashes["sha1"] = "invalid"

    helper = write_fake_dolphin(
        tmp_path / "dolphin-tool",
        header=GC_HEADER,
        hashes=hashes,
    )

    image = tmp_path / "disc.rvz"
    image.write_bytes(b"synthetic-rvz")

    with pytest.raises(DolphinResponseError):
        DolphinAdapter(
            executable=str(helper),
        ).identify(image)


def test_invalid_header_json_is_rejected(
    tmp_path: Path,
) -> None:
    helper = tmp_path / "dolphin-tool"

    helper.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'not-json'\n"
        "exit 0\n"
    )
    helper.chmod(0o755)

    image = tmp_path / "disc.rvz"
    image.write_bytes(b"synthetic-rvz")

    with pytest.raises(DolphinResponseError):
        DolphinAdapter(
            executable=str(helper),
        ).identify(image)


def test_supports_regular_file(tmp_path: Path) -> None:
    image = tmp_path / "disc.rvz"
    image.write_bytes(b"synthetic-rvz")

    adapter = DolphinAdapter()

    assert adapter.supports(image) is True
    assert adapter.supports(
        tmp_path / "missing.rvz"
    ) is False


def test_dolphin_platform_detector_detects_gamecube(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.detection import (
        PlatformDetector,
    )
    from rom_metadata_framework.dolphin import (
        DolphinPlatformDetector,
    )

    helper = write_fake_dolphin(
        tmp_path / "dolphin-tool",
        header=GC_HEADER,
    )

    image = tmp_path / "disc.rvz"
    image.write_bytes(b"synthetic-rvz")

    detector = DolphinPlatformDetector(
        executable=str(helper),
    )

    assert isinstance(
        detector,
        PlatformDetector,
    )

    detection = detector.detect(image)

    assert detection.best is not None
    assert detection.best.platform == "gamecube"
    assert detection.best.confidence == 100

    evidence = detection.best.evidence[0]

    assert evidence.source == "dolphin"
    assert evidence.method == "disc-header"
    assert evidence.value == "GALE01"
    assert evidence.details["revision"] == "2"


def test_dolphin_platform_detector_detects_wii(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.dolphin import (
        DolphinPlatformDetector,
    )

    helper = write_fake_dolphin(
        tmp_path / "dolphin-tool",
        header=WII_HEADER,
    )

    image = tmp_path / "disc.rvz"
    image.write_bytes(b"synthetic-rvz")

    detection = DolphinPlatformDetector(
        executable=str(helper),
    ).detect(image)

    assert detection.best is not None
    assert detection.best.platform == "wii"

    evidence = detection.best.evidence[0]

    assert evidence.value == "RMCE01"
    assert (
        evidence.details["title_id"]
        == "281493537375045"
    )


def test_dolphin_platform_detector_returns_unresolved_on_failure(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.dolphin import (
        DolphinPlatformDetector,
    )

    helper = tmp_path / "dolphin-tool"
    helper.write_text(
        "#!/bin/sh\n"
        "exit 2\n"
    )
    helper.chmod(0o755)

    image = tmp_path / "not-a-disc.rvz"
    image.write_bytes(b"synthetic-data")

    detection = DolphinPlatformDetector(
        executable=str(helper),
    ).detect(image)

    assert detection.best is None
    assert detection.candidates == ()
