from app.domain.exceptions import InvalidInputError
from app.domain.validation import require_range, require_text


class ITService:
    """A business IT service (Payments, VPN, Email...).

    Aggregation: a service *refers to* the services it depends on by id; those
    services exist independently of it.
    """

    def __init__(
        self,
        *,
        id: int | None,
        code: str,
        name: str,
        business_criticality: int,
        owner_team: str = "General",
        description: str = "",
        is_active: bool = True,
        depends_on: set[int] | None = None,
    ) -> None:
        self._id = id
        self._code = require_text(code, "code", min_len=2, max_len=30).upper()
        self._name = require_text(name, "name", min_len=2, max_len=100)
        self._business_criticality = require_range(business_criticality, "business_criticality", 1, 4)
        self._owner_team = require_text(owner_team, "owner_team", max_len=60)
        self._description = (description or "").strip()
        self._is_active = is_active
        self._depends_on: set[int] = set(depends_on or ())

    @property
    def id(self) -> int | None:
        return self._id

    @property
    def code(self) -> str:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    @property
    def business_criticality(self) -> int:
        return self._business_criticality

    @property
    def owner_team(self) -> str:
        return self._owner_team

    @property
    def description(self) -> str:
        return self._description

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def depends_on(self) -> frozenset[int]:
        return frozenset(self._depends_on)

    def assign_id(self, new_id: int) -> None:
        self._id = new_id

    def update(
        self,
        *,
        name: str | None = None,
        business_criticality: int | None = None,
        owner_team: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> None:
        if name is not None:
            self._name = require_text(name, "name", min_len=2, max_len=100)
        if business_criticality is not None:
            self._business_criticality = require_range(business_criticality, "business_criticality", 1, 4)
        if owner_team is not None:
            self._owner_team = require_text(owner_team, "owner_team", max_len=60)
        if description is not None:
            self._description = description.strip()
        if is_active is not None:
            self._is_active = is_active

    def set_dependencies(self, service_ids: set[int]) -> None:
        if self._id is not None and self._id in service_ids:
            raise InvalidInputError("A service cannot depend on itself")
        self._depends_on = set(service_ids)
