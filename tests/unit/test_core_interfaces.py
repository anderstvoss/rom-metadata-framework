from pathlib import Path

from rom_metadata_framework.adapters import IdentificationAdapter
from rom_metadata_framework.hashing import GenericHashAdapter, hash_file
from rom_metadata_framework.resolvers import MetadataResolver, ResolvedMetadata


def test_generic_hash_adapter_matches_protocol() -> None:
    adapter = GenericHashAdapter()

    assert isinstance(adapter, IdentificationAdapter)


def test_resolved_metadata_normalizes_fields() -> None:
    metadata = ResolvedMetadata(
        title="  Example Game ",
        provider=" example-provider ",
        platform=" test ",
        external_ids={"game-id": " 1234 "},
    )

    assert metadata.title == "Example Game"
    assert metadata.provider == "example-provider"
    assert metadata.platform == "test"
    assert metadata.external_ids["game-id"] == "1234"


def test_resolver_protocol_can_be_implemented() -> None:
    class ExampleResolver:
        name = "example"

        def resolve(self, identity):
            return None

    assert isinstance(ExampleResolver(), MetadataResolver)


def test_hash_file_known_content(tmp_path: Path) -> None:
    path = tmp_path / "example.bin"
    path.write_bytes(b"123456789")

    hashes = hash_file(path)

    assert hashes.crc32 == "cbf43926"
    assert hashes.md5 == "25f9e794323b453885f5181f1b624d0b"
    assert hashes.sha1 == "f7c3bc1d808e04732adf679965ccc34ca7ae3441"


def test_generic_hash_adapter_identifies_extension(tmp_path: Path) -> None:
    path = tmp_path / "example.ROM"
    path.write_bytes(b"example")

    identity = GenericHashAdapter().identify(path)

    assert identity.format == "rom"
    assert identity.adapter is not None
    assert identity.adapter.name == "generic-hash"


def test_hash_file_rejects_invalid_chunk_size(tmp_path: Path) -> None:
    path = tmp_path / "example.bin"
    path.write_bytes(b"example")

    try:
        hash_file(path, chunk_size=0)
    except ValueError as exc:
        assert "chunk_size" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_hash_file_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")

    hashes = hash_file(path)

    assert hashes.crc32 == "00000000"
    assert hashes.md5 == "d41d8cd98f00b204e9800998ecf8427e"
    assert hashes.sha1 == "da39a3ee5e6b4b0d3255bfef95601890afd80709"


def test_hash_file_is_independent_of_chunk_size(tmp_path: Path) -> None:
    path = tmp_path / "example.bin"
    path.write_bytes(b"abcdef" * 1000)

    small_chunks = hash_file(path, chunk_size=7)
    large_chunks = hash_file(path, chunk_size=4096)

    assert small_chunks == large_chunks


def test_hash_file_rejects_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.bin"

    try:
        hash_file(path)
    except FileNotFoundError as exc:
        assert exc.args[0] == path
    else:
        raise AssertionError("expected FileNotFoundError")


def test_resolved_metadata_external_ids_are_immutable() -> None:
    metadata = ResolvedMetadata(
        title="Example Game",
        provider="example-provider",
        external_ids={"game-id": "1234"},
    )

    try:
        metadata.external_ids["game-id"] = "5678"
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")
