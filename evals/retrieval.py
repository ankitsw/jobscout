import numpy as np


def recall_at_k(ranked_ids: list[int], relevant_ids: set[int], k: int) -> float:
    """ ranked_ids: predicted rank order of document ids.
        relevant_ids: set of relevant document ids.
        k: cutoff rank.
        
        Returns the recall at k, which is the proportion of relevant documents that are retrieved in the top k results."""
    if not relevant_ids:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def mrr(ranked_ids: list[int], relevant_ids: set[int]) -> float:
    """ ranked_ids: predicted rank order of document ids.
        relevant_ids: set of relevant document ids.
        
        Returns the mean reciprocal rank."""
    for i, doc_id in enumerate(ranked_ids, 1):
        if doc_id in relevant_ids:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked_labels: list[int], k: int) -> float:
    """ranked_labels: graded relevance (0-3) in predicted rank order.
    k: cutoff rank.
    Returns the normalized discounted cumulative gain at k."""
    gains = np.array(ranked_labels[:k], dtype=float)
    if len(gains) == 0:
        return 0.0
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float((2**gains - 1) @ discounts)
    ideal = np.sort(np.array(ranked_labels, dtype=float))[::-1][:k]
    idcg = float((2**ideal - 1) @ discounts[: len(ideal)])
    return dcg / idcg if idcg > 0 else 0.0
