from __future__ import annotations

import hashlib
import zlib
from pathlib import Path

from .identity import AdapterProvenance, HashSet, RomIdentity


DEFAULT_CHUNK_SIZE = 1024 * 1024


def hash_file(
    path: Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> HashSet:
    """Calculate CRC32, MD5, and SHA-1 for one file in a single pass."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(path)

    crc32 = 0
    md5 = hashlib.md5(usedforsecurity=False)
    sha1 = hashlib.sha1(usedforsecurity=False)

    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            crc32 = zlib.crc32(chunk, crc32)
            md5.update(chunk)
            sha1.update(chunk)

    return HashSet(
        crc32=f"{crc32 & 0xFFFFFFFF:08x}",
        md5=md5.hexdigest(),
        sha1=sha1.hexdigest(),
    )


class GenericHashAdapter:
    """Generic adapter that hashes any regular file without parsing its format."""

    name = "generic-hash"

    def supports(self, path: Path) -> bool:
        return Path(path).is_file()

    def identify(self, path: Path) -> RomIdentity:
        path = Path(path)

        return RomIdentity(
            format=path.suffix.lower().lstrip(".") or None,
            hashes=hash_file(path),
            adapter=AdapterProvenance(
                name=self.name,
                backend="python-standard-library",
            ),
        )
