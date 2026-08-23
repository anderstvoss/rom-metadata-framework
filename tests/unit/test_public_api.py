import rom_metadata_framework as rmf

EXPECTED_PUBLIC_API = {
    "DEFAULT_VERIFICATION_POLICY",
    "AgeRating",
    "CanonicalReleaseIdentity",
    "ExternalIdentifier",
    "HashSet",
    "IdentificationResult",
    "IdentificationVerification",
    "LocalContentMetadata",
    "LocalIdentifier",
    "LocalMetadataProvenance",
    "LocalMetadataValue",
    "LocalPlayerCount",
    "LocalTimestamp",
    "MediaReference",
    "MetadataEnrichmentResult",
    "MetadataFieldReconciliation",
    "MetadataFieldReconciliationStatus",
    "MetadataProvenance",
    "MetadataReconciliationReport",
    "MetadataValue",
    "NamingPolicy",
    "NormalizedContentIdentity",
    "PlatformCandidate",
    "PlatformDefinition",
    "PlatformDetection",
    "PlatformEvidence",
    "PlatformReconciliation",
    "PlatformReconciliationStatus",
    "PlayerCount",
    "ReleaseDate",
    "ReleaseMetadata",
    "ReleaseReconciliation",
    "ReleaseReconciliationStatus",
    "RenamePlan",
    "RepresentationIdentity",
    "RomIdentity",
    "RuntimeCapability",
    "RuntimeCapabilityStatus",
    "UnsupportedPlatformBackendError",
    "UnknownPlatformError",
    "VerificationPolicy",
    "VerificationReport",
    "VerificationStatus",
    "canonical_platform_name",
    "collect_identification_metadata",
    "identify_file",
    "resolve_platform",
    "verify_identification",
}


EXCLUDED_ROOT_API = {
    "AdapterProvenance",
    "AmbiguousNormalizerError",
    "BackendPlatformMapping",
    "BackendResult",
    "BackendSpec",
    "CompositeNormalizer",
    "DolphinAdapter",
    "IdentificationEvidence",
    "MetadataCollectionReport",
    "MetadataProvider",
    "MetadataProviderCollection",
    "MetadataProviderResult",
    "NesAdapter",
    "NormalizerProbe",
    "NormalizerProbeStatus",
    "PlatformDetector",
    "RcheevosAdapter",
    "XboxAdapter",
    "backend_platform_identifier",
    "backend_platform_mapping",
    "probe_backend",
    "reconcile_metadata",
    "reconcile_platform",
    "reconcile_release_matches",
    "run_backend",
    "verify_release",
}


def test_root_public_api_is_explicit() -> None:
    assert set(rmf.__all__) == EXPECTED_PUBLIC_API


def test_every_public_symbol_is_available() -> None:
    for name in rmf.__all__:
        assert hasattr(rmf, name), name


def test_implementation_and_lower_level_symbols_are_not_root_exports() -> None:
    assert not EXCLUDED_ROOT_API & set(rmf.__all__)


def test_excluded_symbols_are_not_incidental_root_attributes() -> None:
    for name in EXCLUDED_ROOT_API:
        assert not hasattr(rmf, name), name


def test_root_models_reference_canonical_module_objects() -> None:
    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.identity import (
        HashSet,
        RomIdentity,
    )
    from rom_metadata_framework.representation import (
        RepresentationIdentity,
    )

    assert rmf.HashSet is HashSet
    assert rmf.RomIdentity is RomIdentity
    assert rmf.NormalizedContentIdentity is NormalizedContentIdentity
    assert rmf.RepresentationIdentity is RepresentationIdentity


def test_primary_workflows_are_root_exports() -> None:
    assert callable(rmf.identify_file)
    assert callable(rmf.verify_identification)
    assert callable(rmf.collect_identification_metadata)
    assert callable(rmf.resolve_platform)
    assert callable(rmf.canonical_platform_name)
