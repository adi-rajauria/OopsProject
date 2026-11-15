"""Text similarity behind an interface, so the rest of the system never imports scikit-learn."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class TextSimilarity(ABC):
    @abstractmethod
    def scores(self, query: str, documents: Sequence[str]) -> list[float]:
        """Similarity in [0, 1] between the query and each document (same order)."""


class TfidfTextSimilarity(TextSimilarity):
    """TF-IDF over character n-grams (3-5, word-bounded) + cosine similarity.

    Character n-grams were chosen over word TF-IDF after calibration: they match
    word variants ("payment"/"payments"/"pay") that short incident titles rely on
    (see docs/ALGORITHMS.md). The vectorizer is fitted on the query plus the
    candidates, so IDF reflects only the texts being compared.
    """

    def __init__(self, ngram_range: tuple[int, int] = (3, 5)) -> None:
        self._ngram_range = ngram_range

    def scores(self, query: str, documents: Sequence[str]) -> list[float]:
        if not documents or not query.strip():
            return [0.0] * len(documents)
        vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=self._ngram_range, sublinear_tf=True, lowercase=True
        )
        try:
            matrix = vectorizer.fit_transform([query, *documents])
        except ValueError:  # empty vocabulary (e.g. only punctuation)
            return [0.0] * len(documents)
        return [round(float(s), 3) for s in cosine_similarity(matrix[0], matrix[1:]).ravel()]


def incident_text(title: str, description: str) -> str:
    """Title counts twice: it is the most informative part of a short report."""
    return f"{title}. {title}. {description}"
