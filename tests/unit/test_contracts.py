
from rom_metadata_framework.contracts import (
    FrameworkContractError,
    MetadataProviderContractError,
    NormalizerContractError,
)


def test_normalizer_contract_error_exposes_context() -> None:
    error = NormalizerContractError(
        "invalid normalizer result",
        component="ExampleNormalizer",
        operation="identify",
        field="content",
    )

    assert isinstance(error, FrameworkContractError)
    assert error.component == "ExampleNormalizer"
    assert error.operation == "identify"
    assert error.field == "content"
    assert str(error) == "invalid normalizer result"


def test_normalizer_contract_error_field_is_optional() -> None:
    error = NormalizerContractError(
        "invalid normalizer contract",
        component="CompositeNormalizer",
        operation="register",
    )

    assert error.field is None



def test_metadata_provider_contract_error_exposes_context() -> None:
    error = MetadataProviderContractError(
        "invalid metadata provider result",
        component="provider-a",
        operation="lookup_metadata",
        field="provider",
    )

    assert isinstance(error, FrameworkContractError)
    assert error.component == "provider-a"
    assert error.operation == "lookup_metadata"
    assert error.field == "provider"
