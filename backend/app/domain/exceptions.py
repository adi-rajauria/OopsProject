"""Custom exception hierarchy. One class per error situation listed in the spec.

The API layer maps each family to an HTTP status in one place (app/core/errors.py),
so the domain never knows about HTTP.
"""

from typing import Any


class ITSMError(Exception):
    """Root of every business/infrastructure error raised by the application."""

    code: str = "ITSM_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


# --- Authentication / authorization -------------------------------------------------------

class AuthenticationError(ITSMError):
    code = "AUTHENTICATION_FAILED"


class InvalidCredentialsError(AuthenticationError):
    """Spec: invalid login."""

    code = "INVALID_CREDENTIALS"

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InvalidTokenError(AuthenticationError):
    code = "INVALID_TOKEN"


class UnauthorizedOperationError(ITSMError):
    """Spec: unauthorized operation (authenticated, but not allowed)."""

    code = "UNAUTHORIZED_OPERATION"


# --- Validation --------------------------------------------------------------------------

class InvalidInputError(ITSMError):
    """Spec: invalid user input."""

    code = "INVALID_INPUT"


class InvalidIncidentError(InvalidInputError):
    """Spec: invalid incident (incident data violates business rules)."""

    code = "INVALID_INCIDENT"


class InvalidStateTransitionError(ITSMError):
    """Spec: invalid state transition (e.g. NEW -> CLOSED)."""

    code = "INVALID_STATE_TRANSITION"

    def __init__(self, current_state: str, action: str) -> None:
        super().__init__(
            f"Cannot '{action}' an incident in state {current_state}",
            details={"current_state": current_state, "action": action},
        )
        self.current_state = current_state
        self.action = action


# --- Not found / conflicts -----------------------------------------------------------------

class NotFoundError(ITSMError):
    code = "NOT_FOUND"
    entity: str = "Entity"

    def __init__(self, identifier: object) -> None:
        super().__init__(f"{self.entity} '{identifier}' not found", details={"id": str(identifier)})


class IncidentNotFoundError(NotFoundError):
    code = "INCIDENT_NOT_FOUND"
    entity = "Incident"


class ServiceNotFoundError(NotFoundError):
    """Spec: service not found."""

    code = "SERVICE_NOT_FOUND"
    entity = "Service"


class UserNotFoundError(NotFoundError):
    code = "USER_NOT_FOUND"
    entity = "User"


class CategoryNotFoundError(NotFoundError):
    code = "CATEGORY_NOT_FOUND"
    entity = "Category"


class SLAPolicyNotFoundError(NotFoundError):
    code = "SLA_POLICY_NOT_FOUND"
    entity = "SLA policy"


class ConflictError(ITSMError):
    code = "CONFLICT"


class EmailAlreadyRegisteredError(ConflictError):
    code = "EMAIL_ALREADY_REGISTERED"

    def __init__(self, email: str) -> None:
        super().__init__(f"Email '{email}' is already registered")


class DuplicateIncidentError(ConflictError):
    """Spec: duplicate incident. Carries the matching incident numbers for the UI."""

    code = "DUPLICATE_INCIDENT"

    def __init__(self, matches: list[dict[str, Any]]) -> None:
        super().__init__(
            "A very similar incident was reported by you recently; resubmit with force=true to create anyway",
            details={"matches": matches},
        )


class FeedbackAlreadySubmittedError(ConflictError):
    code = "FEEDBACK_ALREADY_SUBMITTED"


# --- Assignment ---------------------------------------------------------------------------

class AssignmentError(ITSMError):
    code = "ASSIGNMENT_FAILED"


class TechnicianUnavailableError(AssignmentError):
    """Spec: technician unavailable."""

    code = "TECHNICIAN_UNAVAILABLE"


class TechnicianWorkloadExceededError(AssignmentError):
    """Spec: technician workload exceeded."""

    code = "TECHNICIAN_WORKLOAD_EXCEEDED"

    def __init__(self, technician_name: str, active: int, limit: int) -> None:
        super().__init__(
            f"{technician_name} already has {active} active incidents (limit {limit})",
            details={"active": active, "limit": limit},
        )


# --- Configuration ------------------------------------------------------------------------

class MissingSLAConfigurationError(ITSMError):
    """Spec: missing SLA configuration."""

    code = "MISSING_SLA_CONFIGURATION"

    def __init__(self, priority: str, service_id: int | None) -> None:
        super().__init__(
            f"No SLA policy configured for priority {priority} (service {service_id}) and no default policy",
            details={"priority": priority, "service_id": service_id},
        )


# --- Infrastructure -----------------------------------------------------------------------

class InfrastructureError(ITSMError):
    code = "INFRASTRUCTURE_ERROR"


class PersistenceError(InfrastructureError):
    """Spec: database failure."""

    code = "DATABASE_FAILURE"


class NotificationDeliveryError(InfrastructureError):
    """Spec: network failure while delivering a notification."""

    code = "NOTIFICATION_DELIVERY_FAILED"
