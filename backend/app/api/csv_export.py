"""CSV downloads for search results and reports (presentation concern, so it lives in the API layer)."""

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import datetime

from fastapi.responses import Response

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: object) -> str:
    """Text for one cell. Values that a spreadsheet would run as a formula (e.g. a title starting with "=")
    get a leading apostrophe, which blocks CSV/formula injection when the file is opened in Excel."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    text = str(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def csv_response(filename: str, header: Sequence[str], rows: Iterable[Sequence[object]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows([_cell(v) for v in row] for row in rows)
    # UTF-8 with BOM so Excel shows names like "Zoë" correctly.
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
