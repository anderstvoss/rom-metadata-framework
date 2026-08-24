from __future__ import annotations

import os
from pathlib import Path


class FileOperationError(RuntimeError):
    """Base error for guarded filesystem mutation."""


class DestinationExistsError(FileOperationError):
    """Raised when a rename destination already exists."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

        super().__init__(
            f"destination already exists: {self.path}"
        )


class CrossDirectoryRenameError(FileOperationError):
    """Raised when executable naming leaves the source directory."""


class InvalidRenameSourceError(FileOperationError):
    """Raised when the rename source is not a normal regular file."""


def rename_file_no_overwrite(
    source: Path,
    destination: Path,
) -> None:
    """Rename one regular file without overwriting an existing path.

    The destination is created as a hard link first. Link creation is an
    atomic no-replace operation on supported filesystems. The source name is
    then removed. Because canonical naming always remains in the same
    directory, source and destination are necessarily on the same filesystem.

    Filesystems that cannot create hard links fail rather than falling back to
    an overwrite-capable rename primitive.
    """

    source = Path(source)
    destination = Path(destination)

    if source.parent != destination.parent:
        raise CrossDirectoryRenameError(
            "executable canonical rename must remain "
            "within the source directory"
        )

    if source == destination:
        return

    # Canonical rename acts on the physical file named by SOURCE, not on
    # symbolic-link aliases. Reject symlinks explicitly because Path.is_file()
    # follows them.
    if source.is_symlink():
        raise InvalidRenameSourceError(
            f"rename source must not be a symbolic link: {source}"
        )

    if not source.is_file():
        raise InvalidRenameSourceError(
            f"rename source must be a regular file: {source}"
        )

    # os.path.lexists() also catches dangling symlinks. Path.exists() would
    # incorrectly report those destinations as absent.
    if os.path.lexists(destination):
        raise DestinationExistsError(
            destination
        )

    try:
        os.link(
            source,
            destination,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        raise DestinationExistsError(
            destination
        ) from exc

    try:
        source.unlink()
    except BaseException:
        try:
            destination.unlink()
        except OSError:
            pass

        raise
