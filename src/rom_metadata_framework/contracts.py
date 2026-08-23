from __future__ import annotations


class FrameworkContractError(RuntimeError):
    """Base error for violated framework component contracts."""

    def __init__(
        self,
        message: str,
        *,
        component: str,
        operation: str,
    ) -> None:
        super().__init__(message)
        self.component = component
        self.operation = operation


class NormalizerContractError(FrameworkContractError):
    """Raised when a normalizer violates its declared contract."""

    def __init__(
        self,
        message: str,
        *,
        component: str,
        operation: str,
        field: str | None = None,
    ) -> None:
        super().__init__(
            message,
            component=component,
            operation=operation,
        )
        self.field = field



class InspectionContractError(FrameworkContractError):
    """Raised when a structural inspector violates its contract."""

    def __init__(
        self,
        message: str,
        *,
        component: str,
        operation: str,
        field: str | None = None,
    ) -> None:
        super().__init__(
            message,
            component=component,
            operation=operation,
        )
        self.field = field


class StructuralEvidenceConflictError(FrameworkContractError):
    """Raised when independent structural evidence disagrees."""

    def __init__(
        self,
        message: str,
        *,
        field: str,
    ) -> None:
        super().__init__(
            message,
            component="identify_file",
            operation="reconcile-structural-evidence",
        )
        self.field = field


class MetadataProviderContractError(FrameworkContractError):
    """Raised when a metadata provider violates its declared contract."""

    def __init__(
        self,
        message: str,
        *,
        component: str,
        operation: str,
        field: str | None = None,
    ) -> None:
        super().__init__(
            message,
            component=component,
            operation=operation,
        )
        self.field = field
