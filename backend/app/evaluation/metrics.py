"""Standard ranking metrics. Input is a list of relevance grades (0-3) in ranked order."""
import math

RELEVANT = 2  # grade >= 2 counts as "relevant" for precision, recall and MRR


def precision_at_k(ranked_rels: list[int], k: int, threshold: int = RELEVANT) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for r in ranked_rels[:k] if r >= threshold) / k


def recall_at_k(ranked_rels: list[int], k: int, total_relevant: int, threshold: int = RELEVANT) -> float:
    if total_relevant <= 0:
        return 0.0
    return sum(1 for r in ranked_rels[:k] if r >= threshold) / total_relevant


def _dcg(rels: list[int], k: int) -> float:
    return sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))


def ndcg_at_k(ranked_rels: list[int], all_rels: list[int], k: int) -> float:
    """all_rels: grades of EVERY candidate job, used to build the ideal ranking."""
    ideal = _dcg(sorted(all_rels, reverse=True), k)
    return _dcg(ranked_rels, k) / ideal if ideal > 0 else 0.0


def reciprocal_rank(ranked_rels: list[int], threshold: int = RELEVANT) -> float:
    for position, r in enumerate(ranked_rels, start=1):
        if r >= threshold:
            return 1.0 / position
    return 0.0