# D&D 5e Point Buy Enumerator
#
# Generates all unique, Pareto-optimal stat arrays possible under the standard
# 27-point point buy system. Stats are sorted highest-to-lowest; placement across
# the six ability scores is intentionally ignored (that's a separate concern).
#
# Point buy table (scores 8-15, starting budget 27):
#   Score:  8   9  10  11  12  13  14  15
#   Cost:   0   1   2   3   4   5   7   9
#
# A combo is discarded if another valid combo is >= it in every position —
# meaning no unused point could have been placed anywhere. In practice, the
# cost table's structure (gaps only at 13->14 and 14->15) means a stranded
# point is impossible within a 27-point budget, so every surviving combo
# spends exactly 27 points.
#
# --- On Dynamic Programming ---
#
# DP applies when a problem has:
#   1. Overlapping subproblems — the same sub-question is reached by many paths
#   2. Optimal substructure — the answer depends only on *where you are*,
#      not on *how you got there*
#
# The key design decision is identifying the state — the minimal information
# needed to answer a sub-question. Here: (pos, budget, max_val). Two different
# sequences of early choices that land on the same state will have identical
# valid completions, so we compute those completions once and cache them.
#
# The hard part in practice is defining the state correctly before writing code.
# Get it wrong and you either miss cache hits (recomputing) or reuse results
# incorrectly. Get it right and the rest is mechanical.
#
# DP predates programming — it comes from Bellman's 1950s optimization theory.
# It's a mathematical observation that was later implemented in code, not a
# programming trick. That framing helps: the cache is just the implementation
# of "never answer the same sub-question twice."
#
# This script separates generation (DP) from filtering (domination check).
# A smarter approach would prune dominated branches during generation, but
# at this scale (1,197 combos) the post-filter is simpler and runs instantly.

from functools import lru_cache

COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
BUDGET = 27
NUM_STATS = 6


@lru_cache(maxsize=None)
def dp(pos, budget, max_val):
    """
    Return all valid sorted (non-increasing) stat tuples for positions pos..NUM_STATS-1.

    DP insight: many different choices for earlier stats can arrive at the same
    (pos, budget, max_val) state. Memoization means we compute each unique state
    once and reuse the result, instead of rewalking the same subtree repeatedly.
    """
    if pos == NUM_STATS:
        return [()]

    results = []
    for v in range(max_val, 7, -1):  # 15 down to 8, maintaining sorted order
        c = COST[v]
        if c > budget:
            continue
        for suffix in dp(pos + 1, budget - c, v):
            results.append((v,) + suffix)

    return results


def dominates(a, b):
    """True if a is >= b in every position (and they differ somewhere)."""
    return a != b and all(x >= y for x, y in zip(a, b))


all_combos = dp(0, BUDGET, 15)

pareto = [
    a for a in all_combos
    if not any(dominates(b, a) for b in all_combos)
]

pareto.sort(reverse=True)

print(f"Valid combinations within budget:  {len(all_combos)}")
print(f"After removing dominated combos:   {len(pareto)}")
print()
for combo in pareto:
    spent = sum(COST[v] for v in combo)
    print(f"{list(combo)}  (spent: {spent})")
