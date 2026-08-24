from pathlib import Path

import pytest

from rom_metadata_framework.file_operations import (
    CrossDirectoryRenameError,
    DestinationExistsError,
    rename_file_no_overwrite,
)


def test_rename_file_no_overwrite_moves_existing_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "old.iso"
    destination = tmp_path / "new.iso"

    source.write_bytes(b"payload")

    rename_file_no_overwrite(
        source,
        destination,
    )

    assert not source.exists()
    assert destination.read_bytes() == b"payload"


def test_rename_file_no_overwrite_refuses_existing_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "old.iso"
    destination = tmp_path / "new.iso"

    source.write_bytes(b"source")
    destination.write_bytes(b"destination")

    with pytest.raises(
        DestinationExistsError
    ):
        rename_file_no_overwrite(
            source,
            destination,
        )

    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"destination"


def test_rename_file_no_overwrite_same_path_is_noop(
    tmp_path: Path,
) -> None:
    source = tmp_path / "same.iso"
    source.write_bytes(b"payload")

    rename_file_no_overwrite(
        source,
        source,
    )

    assert source.read_bytes() == b"payload"


def test_rename_file_no_overwrite_rejects_other_directory(
    tmp_path: Path,
) -> None:
    source = tmp_path / "old.iso"
    other = tmp_path / "other"
    other.mkdir()
    destination = other / "new.iso"

    source.write_bytes(b"payload")

    with pytest.raises(
        CrossDirectoryRenameError
    ):
        rename_file_no_overwrite(
            source,
            destination,
        )

    assert source.exists()
    assert not destination.exists()


def test_rename_file_no_overwrite_rejects_source_symlink(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.file_operations import (
        InvalidRenameSourceError,
    )

    target = tmp_path / "target.iso"
    source = tmp_path / "alias.iso"
    destination = tmp_path / "renamed.iso"

    target.write_bytes(b"payload")
    source.symlink_to(target)

    with pytest.raises(
        InvalidRenameSourceError
    ):
        rename_file_no_overwrite(
            source,
            destination,
        )

    assert source.is_symlink()
    assert target.read_bytes() == b"payload"
    assert not destination.exists()


def test_rename_file_no_overwrite_refuses_dangling_symlink_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "old.iso"
    destination = tmp_path / "new.iso"

    source.write_bytes(b"source")
    destination.symlink_to(
        tmp_path / "missing-target.iso"
    )

    assert not destination.exists()
    assert destination.is_symlink()

    with pytest.raises(
        DestinationExistsError
    ):
        rename_file_no_overwrite(
            source,
            destination,
        )

    assert source.read_bytes() == b"source"
    assert destination.is_symlink()


def test_rename_file_no_overwrite_rejects_directory_source(
    tmp_path: Path,
) -> None:
    from rom_metadata_framework.file_operations import (
        InvalidRenameSourceError,
    )

    source = tmp_path / "source-dir"
    destination = tmp_path / "renamed"

    source.mkdir()

    with pytest.raises(
        InvalidRenameSourceError
    ):
        rename_file_no_overwrite(
            source,
            destination,
        )

    assert source.is_dir()
    assert not destination.exists()
