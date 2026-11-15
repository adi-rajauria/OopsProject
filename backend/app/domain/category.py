from app.domain.validation import require_text


class Category:
    """Incident category. Categories are data, not code: adding one (with keywords)
    needs no code change anywhere else (Open/Closed)."""

    def __init__(
        self,
        *,
        id: int | None,
        code: str,
        name: str,
        keywords: tuple[str, ...] | list[str] = (),
        is_active: bool = True,
    ) -> None:
        self._id = id
        self._code = require_text(code, "code", min_len=2, max_len=30).upper()
        self._name = require_text(name, "name", min_len=2, max_len=60)
        self._keywords = self._clean_keywords(keywords)
        self._is_active = is_active

    @staticmethod
    def _clean_keywords(keywords: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        # dict.fromkeys keeps insertion order while removing duplicates
        return tuple(dict.fromkeys(k.strip().lower() for k in keywords if k and k.strip()))

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
    def keywords(self) -> tuple[str, ...]:
        return self._keywords

    @property
    def is_active(self) -> bool:
        return self._is_active

    def assign_id(self, new_id: int) -> None:
        self._id = new_id

    def update(self, *, name: str | None = None, keywords: list[str] | None = None,
               is_active: bool | None = None) -> None:
        if name is not None:
            self._name = require_text(name, "name", min_len=2, max_len=60)
        if keywords is not None:
            self._keywords = self._clean_keywords(keywords)
        if is_active is not None:
            self._is_active = is_active
