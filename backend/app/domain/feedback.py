from dataclasses import dataclass
from datetime import datetime

from app.domain.exceptions import InvalidInputError


@dataclass(frozen=True)
class Feedback:
    incident_id: int
    employee_id: int
    rating: int
    comment: str
    created_at: datetime
    id: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.rating, bool) or not isinstance(self.rating, int) or not 1 <= self.rating <= 5:
            raise InvalidInputError("Rating must be an integer from 1 to 5", details={"field": "rating"})
        if len(self.comment) > 2000:
            raise InvalidInputError("Feedback comment is too long", details={"field": "comment"})

