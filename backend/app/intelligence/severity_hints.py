"""Impact / urgency hints from the report text, so employees rate severity consistently.

Each rule is a phrase pattern that implies a level on the 1-4 scale; the highest matching level wins and the matched
phrase is the explanation. Only a hint: the reporter's own choice is what gets submitted.
"""

import re
from dataclasses import dataclass

# (level, phrase patterns) - word-bounded, case-insensitive. Highest level first.
IMPACT_RULES: tuple[tuple[int, tuple[str, ...]], ...] = (
    (4, (r"all (users|customers|staff|employees|regions)", r"every(one|body)", r"(whole|entire) (company|organi[sz]ation)",
         r"company[- ]wide", r"customers")),
    (3, (r"(whole|entire) (department|team|floor|building|site|office)", r"multiple (floors|teams|departments)",
         r"all of (finance|sales|hr|operations)", r"department", r"nobody can")),
    (2, (r"colleagues", r"several (people|users|staff|agents)", r"a few (people|users|of us)", r"my team", r"some users")),
    (1, (r"only me", r"just me", r"my (laptop|computer|pc|keyboard|mouse|monitor|account)")),
)
URGENCY_RULES: tuple[tuple[int, tuple[str, ...]], ...] = (
    (4, (r"cannot pay", r"unable to (pay|make a payment|complete transactions)", r"(is|are|went|goes|completely) down",
         r"outage", r"unavailable", r"breach", r"hacked", r"data loss", r"(losing|lost) (money|revenue|data)",
         r"transactions? fail")),
    (3, (r"blocked", r"cannot work", r"can't work", r"unable to work", r"urgent", r"asap", r"deadline", r"stopped working",
         r"keeps? (dropping|disconnecting)")),
    (2, (r"slow", r"intermittent(ly)?", r"sometimes", r"delayed")),
    (1, (r"workaround", r"no rush", r"when (possible|you can)", r"cosmetic", r"minor")),
)


@dataclass(frozen=True)
class SeverityHint:
    impact: int | None
    impact_reason: str | None
    urgency: int | None
    urgency_reason: str | None


def _strongest(text: str, rules: tuple[tuple[int, tuple[str, ...]], ...]) -> tuple[int | None, str | None]:
    for level, patterns in rules:  # highest level first, so the first hit is the strongest
        for pattern in patterns:
            if match := re.search(rf"\b{pattern}\b", text, re.IGNORECASE):
                return level, f'mentions "{match.group(0).lower()}"'
    return None, None


class SeverityAdvisor:
    def suggest(self, title: str, description: str) -> SeverityHint:
        text = f"{title}. {description}"
        impact, impact_reason = _strongest(text, IMPACT_RULES)
        urgency, urgency_reason = _strongest(text, URGENCY_RULES)
        return SeverityHint(impact, impact_reason, urgency, urgency_reason)
