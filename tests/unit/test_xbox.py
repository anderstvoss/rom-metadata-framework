import struct
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rom_metadata_framework.backends import (
    BackendExecutionError,
    BackendResult,
    BackendTimeoutError,
)
from rom_metadata_framework.normalization import (
    NormalizerProbeStatus,
)
from rom_metadata_framework.xbox import (
    XBE_SHA256_NAMESPACE,
    XDVDFS_CHECKSUM_NAMESPACE,
    XboxAdapter,
    XboxResponseError,
    parse_xbe_certificate,
)


def make_xbe(
    *,
    title_id: int = 0x4D530004,
    title: str = "Halo",
    region: int = 0x00000001,
    ratings: int = 0x00000002,
    allowed_media: int = 0x00000002,
    disc_number: int = 0,
    version: int = 9,
) -> bytes:
    image_base = 0x00010000
    certificate_offset = 0x178
    certificate_address = image_base + certificate_offset

    data = bytearray(0x500)

    data[:4] = b"XBEH"

    struct.pack_into(
        "<I",
        data,
        0x104,
        image_base,
    )

    struct.pack_into(
        "<I",
        data,
        0x110,
        certificate_offset,
    )

    struct.pack_into(
        "<I",
        data,
        0x114,
        1000000000,
    )

    struct.pack_into(
        "<I",
        data,
        0x118,
        certificate_address,
    )

    struct.pack_into(
        "<I",
        data,
        certificate_offset,
        0x1D0,
    )

    struct.pack_into(
        "<I",
        data,
        certificate_offset + 0x04,
        1100000000,
    )

    struct.pack_into(
        "<I",
        data,
        certificate_offset + 0x08,
        title_id,
    )

    encoded = title.encode("utf-16le")

    data[certificate_offset + 0x0C : certificate_offset + 0x0C + len(encoded)] = encoded

    struct.pack_into(
        "<I",
        data,
        certificate_offset + 0x9C,
        allowed_media,
    )

    struct.pack_into(
        "<I",
        data,
        certificate_offset + 0xA0,
        region,
    )

    struct.pack_into(
        "<I",
        data,
        certificate_offset + 0xA4,
        ratings,
    )

    struct.pack_into(
        "<I",
        data,
        certificate_offset + 0xA8,
        disc_number,
    )

    struct.pack_into(
        "<I",
        data,
        certificate_offset + 0xAC,
        version,
    )

    return bytes(data)


def test_parse_halo_certificate_fields() -> None:
    certificate = parse_xbe_certificate(make_xbe())

    assert certificate.title_id == "4D530004"
    assert certificate.formatted_title_id == "MS-004"
    assert certificate.title_name == "Halo"

    assert certificate.regions == ("north-america",)

    assert certificate.region_mask == 1
    assert certificate.ratings_mask == 2
    assert certificate.allowed_media_mask == 2

    assert certificate.disc_number == 0
    assert certificate.version == 9

    assert certificate.xbe_timestamp == (
        datetime.fromtimestamp(
            1000000000,
            tz=UTC,
        )
    )


def test_parse_multiregion_certificate() -> None:
    certificate = parse_xbe_certificate(
        make_xbe(
            title_id=0x4156004B,
            title="Gun",
            region=0x7,
            allowed_media=0x202,
            version=1,
        )
    )

    assert certificate.title_id == "4156004B"
    assert certificate.formatted_title_id == "AV-075"

    assert certificate.regions == (
        "north-america",
        "japan",
        "rest-of-world",
    )


def test_parse_kotor_versions_remain_executable_versions() -> None:
    first = parse_xbe_certificate(
        make_xbe(
            title_id=0x4C410003,
            title="Star Wars: KotOR",
            version=95126529,
        )
    )

    revision = parse_xbe_certificate(
        make_xbe(
            title_id=0x4C410003,
            title="Star Wars: KotOR",
            version=95126538,
        )
    )

    assert first.title_id == revision.title_id
    assert first.version != revision.version


@pytest.mark.parametrize(
    "data",
    (
        b"",
        b"not-an-xbe" + bytes(0x200),
    ),
)
def test_invalid_xbe_is_rejected(
    data: bytes,
) -> None:
    with pytest.raises(XboxResponseError):
        parse_xbe_certificate(data)


def test_xiso_representation_detection(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.bin"

    data = bytearray(0x12000)

    data[0x10000 : 0x10000 + len(b"MICROSOFT*XBOX*MEDIA")] = b"MICROSOFT*XBOX*MEDIA"

    path.write_bytes(data)

    assert XboxAdapter._representation(path) == "xiso"


def test_nonzero_descriptor_representation_is_full_disc(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.bin"
    path.write_bytes(bytes(0x12000))

    assert XboxAdapter._representation(path) == "full-disc"


def test_local_metadata_preserves_xbox_fields() -> None:
    certificate = parse_xbe_certificate(make_xbe())

    metadata = XboxAdapter._local_metadata(
        certificate,
        representation="xiso",
        xbe_sha256="a" * 64,
    )

    assert metadata.platform == "xbox"
    assert metadata.titles[0].value == "Halo"

    ids = {item.namespace: item.value for item in metadata.identifiers}

    assert ids["xbox-title-id"] == "4D530004"

    assert ids["xbox-title-id-formatted"] == "MS-004"

    assert ids["xbox-xbe-sha256"] == "a" * 64

    assert metadata.executable_versions[0].value == "9"

    assert metadata.release_revisions == ()

    assert metadata.disc_numbers[0].value == 0

    assert metadata.regions[0].value == "north-america"

    assert metadata.native_metadata["region_mask"] == "0x00000001"

    assert metadata.boot["executable"] == "default.xbe"


def test_checksum_validation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    adapter = XboxAdapter()

    def fake_run_backend(spec, args):
        return BackendResult(
            executable=Path("xdvdfs"),
            arguments=tuple(args),
            stdout="a" * 64 + "\n",
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(
        "rom_metadata_framework.xbox.run_backend",
        fake_run_backend,
    )

    assert adapter._checksum(tmp_path / "unused.iso") == "a" * 64


def test_invalid_checksum_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    adapter = XboxAdapter()

    def fake_run_backend(spec, args):
        return BackendResult(
            executable=Path("xdvdfs"),
            arguments=tuple(args),
            stdout="not-a-checksum\n",
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(
        "rom_metadata_framework.xbox.run_backend",
        fake_run_backend,
    )

    with pytest.raises(
        XboxResponseError,
        match="invalid checksum",
    ):
        adapter._checksum(tmp_path / "unused.iso")


def test_probe_valid_image(
    monkeypatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "image.iso"
    path.write_bytes(bytes(0x12000))

    adapter = XboxAdapter()

    def fake_run_backend(spec, args):
        return BackendResult(
            executable=Path("xdvdfs"),
            arguments=tuple(args),
            stdout=("Valid:               true\nCreation time:       0\n"),
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(
        "rom_metadata_framework.xbox.run_backend",
        fake_run_backend,
    )

    probe = adapter.probe(path)

    assert probe.status is (NormalizerProbeStatus.SUPPORTED)

    assert probe.details["representation"] == "full-disc"


def test_normalized_content_uses_specialized_ids() -> None:
    assert XDVDFS_CHECKSUM_NAMESPACE == "xbox-xdvdfs-checksum"

    assert XBE_SHA256_NAMESPACE == "xbox-xbe-sha256"


def test_probe_execution_rejection_is_unsupported(
    monkeypatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "garbage.bin"
    path.write_bytes(b"garbage")

    adapter = XboxAdapter()

    def fake_run_backend(spec, args):
        raise BackendExecutionError(
            executable="xdvdfs",
            returncode=1,
            stdout="",
            stderr="invalid image",
        )

    monkeypatch.setattr(
        "rom_metadata_framework.xbox.run_backend",
        fake_run_backend,
    )

    probe = adapter.probe(path)

    assert probe.status is (NormalizerProbeStatus.UNSUPPORTED)


def test_probe_timeout_is_backend_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "candidate.iso"
    path.write_bytes(bytes(0x12000))

    adapter = XboxAdapter()

    def fake_run_backend(spec, args):
        raise BackendTimeoutError("xdvdfs timed out")

    monkeypatch.setattr(
        "rom_metadata_framework.xbox.run_backend",
        fake_run_backend,
    )

    probe = adapter.probe(path)

    assert probe.status is (NormalizerProbeStatus.BACKEND_FAILURE)

    assert probe.details["exception"] == ("BackendTimeoutError")


def test_xbox_platform_detector_uses_structural_probe(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.detection import (
        PlatformDetector,
    )
    from rom_metadata_framework.normalization import (
        NormalizerProbe,
        NormalizerProbeStatus,
    )
    from rom_metadata_framework.xbox import (
        XboxPlatformDetector,
    )

    path = tmp_path / "not-an-xbox-extension.bin"
    path.write_bytes(b"candidate")

    detector = XboxPlatformDetector(
        executable="/example/xdvdfs",
    )

    monkeypatch.setattr(
        detector.adapter,
        "probe",
        lambda candidate: NormalizerProbe(
            normalizer="xbox",
            status=NormalizerProbeStatus.SUPPORTED,
            details={
                "representation": "xiso",
            },
        ),
    )

    assert isinstance(
        detector,
        PlatformDetector,
    )

    detection = detector.detect(path)

    assert detection.best is not None
    assert detection.best.platform == "xbox"
    assert detection.best.confidence == 100

    evidence = detection.best.evidence[0]

    assert evidence.source == "xdvdfs"
    assert evidence.method == "filesystem-probe"
    assert evidence.value == "xdvdfs"
    assert evidence.details["representation"] == "xiso"


def test_xbox_platform_detector_returns_unresolved_without_support(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.normalization import (
        NormalizerProbe,
        NormalizerProbeStatus,
    )
    from rom_metadata_framework.xbox import (
        XboxPlatformDetector,
    )

    path = tmp_path / "game.iso"
    path.write_bytes(b"unrelated")

    detector = XboxPlatformDetector(
        executable="/example/xdvdfs",
    )

    monkeypatch.setattr(
        detector.adapter,
        "probe",
        lambda candidate: NormalizerProbe(
            normalizer="xbox",
            status=NormalizerProbeStatus.UNSUPPORTED,
        ),
    )

    detection = detector.detect(path)

    assert detection.best is None
    assert detection.candidates == ()


def test_xbe_certificate_address_before_image_base_is_rejected() -> None:
    data = bytearray(make_xbe())
    struct.pack_into("<I", data, 0x118, 0x0000FFFF)

    with pytest.raises(
        XboxResponseError,
        match="precedes the image base",
    ):
        parse_xbe_certificate(bytes(data))


def test_xbe_certificate_outside_file_is_rejected() -> None:
    data = bytearray(make_xbe())
    struct.pack_into(
        "<I",
        data,
        0x118,
        0x00010000 + len(data),
    )

    with pytest.raises(
        XboxResponseError,
        match="certificate lies outside the file",
    ):
        parse_xbe_certificate(bytes(data))


def test_xbe_short_certificate_is_rejected() -> None:
    data = bytearray(make_xbe())
    struct.pack_into("<I", data, 0x178, 0xAF)

    with pytest.raises(
        XboxResponseError,
        match="certificate is shorter than required fields",
    ):
        parse_xbe_certificate(bytes(data))


def test_xbe_invalid_utf16_title_is_rejected() -> None:
    data = bytearray(make_xbe())
    data[0x184:0x188] = bytes((0x00, 0xD8, 0x00, 0x00))

    with pytest.raises(
        XboxResponseError,
        match="title name is not valid UTF-16LE",
    ):
        parse_xbe_certificate(bytes(data))


def test_xbe_certificate_pointer_remains_authoritative() -> None:
    data = bytearray(make_xbe())
    struct.pack_into("<I", data, 0x110, 0x200)

    certificate = parse_xbe_certificate(bytes(data))

    assert certificate.title_name == "Halo"
    assert certificate.title_id == "4D530004"


def test_xbe_alternate_title_ids_are_preserved() -> None:
    data = bytearray(make_xbe())
    struct.pack_into("<I", data, 0x178 + 0x5C, 0x12345678)

    certificate = parse_xbe_certificate(bytes(data))

    assert certificate.alternate_title_ids == ("12345678",)


def test_xbe_non_ascii_title_prefix_uses_hex() -> None:
    certificate = parse_xbe_certificate(
        make_xbe(title_id=0x01020003)
    )

    assert certificate.formatted_title_id == "0102-003"
