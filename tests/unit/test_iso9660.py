from pathlib import Path

import pytest

from rom_metadata_framework.iso9660 import (
    BoundedIso9660,
    Iso9660FormatError,
)


def test_bounded_iso9660_rejects_non_iso(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ordinary.bin"
    path.write_bytes(b"ordinary")

    with pytest.raises(
        Iso9660FormatError,
        match="primary volume descriptor",
    ):
        BoundedIso9660(path)


def test_bounded_iso9660_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        Iso9660FormatError,
        match="regular file",
    ):
        BoundedIso9660(
            tmp_path / "missing.iso"
        )
