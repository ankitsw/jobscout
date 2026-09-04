from evals.retrieval import recall_at_k, mrr, ndcg_at_k


# ---- recall_at_k ----

def test_recall_perfect():
    # ranked list: [1, 2, 3], relevant items: {1, 2, 3}, look at top 3
    # all 3 relevant items found in top 3 → 3/3 = 1.0
    assert recall_at_k([1, 2, 3], {1, 2, 3}, k=3) == 1.0


def test_recall_partial():
    # ranked list: [9, 1, 2], relevant items: {1, 2, 3}, look at top 3
    # only items 1 and 2 found, item 3 is missing → 2/3
    assert recall_at_k([9, 1, 2], {1, 2, 3}, k=3) == 2 / 3


def test_recall_zero():
    # ranked list: [7, 8, 9], relevant items: {1, 2, 3}, look at top 3
    # none of the relevant items appear → 0/3 = 0.0
    assert recall_at_k([7, 8, 9], {1, 2, 3}, k=3) == 0.0


def test_recall_empty_relevant_set():
    # there are no relevant items at all — should return 0.0, not crash
    assert recall_at_k([1, 2, 3], set(), k=3) == 0.0


# ---- mrr ----

def test_mrr_first_position():
    # first relevant item is at position 1 → 1/1 = 1.0
    assert mrr([1, 2, 3], {1}) == 1.0


def test_mrr_third_position():
    # ranked: [9, 8, 1] — first relevant item (1) is at position 3 → 1/3
    assert mrr([9, 8, 1], {1}) == 1 / 3


def test_mrr_no_hit():
    # no relevant item anywhere in the list → 0.0
    assert mrr([9, 8, 7], {1}) == 0.0


# ---- ndcg_at_k ----

def test_ndcg_perfect_ranking():
    # labels already in best possible order: [3, 2, 1, 0]
    # actual DCG == ideal DCG → nDCG = 1.0
    assert ndcg_at_k([3, 2, 1, 0], k=4) == 1.0


def test_ndcg_imperfect_ranking():
    # same labels, worst possible order: [0, 1, 2, 3]
    # puts the best item last — should score below perfect
    score = ndcg_at_k([0, 1, 2, 3], k=4)
    assert score < 1.0
    assert score > 0.0  # not completely zero either, since some gain still exists


def test_ndcg_empty():
    # no labels at all → 0.0
    assert ndcg_at_k([], k=4) == 0.0
