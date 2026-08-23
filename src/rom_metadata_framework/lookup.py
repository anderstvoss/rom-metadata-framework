from __future__ import annotations

from dataclasses import dataclass, field

from .identity import HashSet, RomIdentity


@dataclass(frozen=True, slots=True)
class LookupIdentity:
    """Hash identity supplied to a metadata/catalogue provider."""

    file_name: str
    file_size: int
    hashes: HashSet = field(default_factory=HashSet)

    def __post_init__(self) -> None:
        file_name = self.file_name.strip()

        if not file_name:
            raise ValueError(
                "lookup file_name must not be empty"
            )

        if (
            isinstance(self.file_size, bool)
            or not isinstance(self.file_size, int)
        ):
            raise TypeError(
                "lookup file_size must be an integer"
            )

        if self.file_size < 0:
            raise ValueError(
                "lookup file_size must not be negative"
            )

        object.__setattr__(
            self,
            "file_name",
            file_name,
        )

    @classmethod
    def from_rom_identity(
        cls,
        identity: RomIdentity,
    ) -> LookupIdentity:
        """Create a provider lookup from physical-file identity."""

        if identity.file_name is None:
            raise ValueError(
                "provider lookup requires file_name"
            )

        if identity.file_size is None:
            raise ValueError(
                "provider lookup requires file_size"
            )

        return cls(
            file_name=identity.file_name,
            file_size=identity.file_size,
            hashes=identity.hashes,
        )
