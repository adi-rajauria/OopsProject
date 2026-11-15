"""Feature 5: category suggestion from the incident description.

confidence = 0.6 x keyword score + 0.4 x similarity to that category's history
  keyword score = hits / (hits + 1)  -> 1 hit 0.50, 2 hits 0.67, 3 hits 0.75 (saturating, so
                  more evidence always counts). hits = keyword occurrences in the text, where
                  the title is repeated, so title words weigh double. Keywords are admin data.
  history       = TF-IDF cosine similarity between the text and a per-category
                  document made of its keywords + its most recent past incidents
New categories work immediately through their keywords and improve as history grows.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.category import Category
from app.intelligence.text_similarity import TextSimilarity


@dataclass(frozen=True)
class CategorySuggestion:
    category_id: int
    code: str
    name: str
    confidence: float
    matched_keywords: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class LabelledText:
    category_id: int
    text: str


class CategorySuggester:
    KEYWORD_WEIGHT = 0.6
    HISTORY_WEIGHT = 0.4
    MIN_CONFIDENCE = 0.12
    HISTORY_PER_CATEGORY = 30
    TOP = 3

    def __init__(self, similarity: TextSimilarity) -> None:
        self._similarity = similarity

    @staticmethod
    def _keyword_hits(text: str, category: Category) -> tuple[int, tuple[str, ...]]:
        """(total occurrences, distinct matched keywords); prefix match so 'printers' hits 'printer'."""
        lowered = text.lower()
        counts = {k: len(re.findall(rf"\b{re.escape(k)}", lowered)) for k in category.keywords}
        return sum(counts.values()), tuple(k for k, n in counts.items() if n)

    def suggest(
        self, text: str, categories: Sequence[Category], history: Sequence[LabelledText] = ()
    ) -> list[CategorySuggestion]:
        active = [c for c in categories if c.is_active]
        if not text.strip() or not active:
            return []
        by_category: dict[int, list[str]] = defaultdict(list)
        for item in history:
            if len(by_category[item.category_id]) < self.HISTORY_PER_CATEGORY:
                by_category[item.category_id].append(item.text)
        documents = [" ".join([*c.keywords, *by_category[c.id]]) for c in active]
        history_scores = self._similarity.scores(text, documents)

        suggestions = []
        for category, history_score in zip(active, history_scores):
            hits, keywords = self._keyword_hits(text, category)
            keyword_score = hits / (hits + 1)
            confidence = round(self.KEYWORD_WEIGHT * keyword_score + self.HISTORY_WEIGHT * history_score, 3)
            if confidence >= self.MIN_CONFIDENCE:
                suggestions.append(
                    CategorySuggestion(
                        category.id,
                        category.code,
                        category.name,
                        confidence,
                        keywords,
                        self._reason(keywords, len(by_category[category.id]), history_score),
                    )
                )
        suggestions.sort(key=lambda s: -s.confidence)
        return suggestions[: self.TOP]

    @staticmethod
    def _reason(keywords: tuple[str, ...], history_size: int, history_score: float) -> str:
        parts = [f"keywords: {', '.join(keywords)}"] if keywords else ["no keyword match"]
        parts.append(f"text similarity {history_score:.2f} to {history_size} past incident(s)")
        return "; ".join(parts)
