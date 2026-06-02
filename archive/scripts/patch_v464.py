#!/usr/bin/env python3
"""Patch v464: Strong CB-aware greedy with cb_w=8 and cb_w=12.

Current CB-aware greedy uses cb_w=3/4/5 which only gives a mild consolidation
bonus. With cb_w=8-12, the bonus becomes strong enough to override small load
differences, potentially producing solutions with much lower CB at the cost of
slightly worse load balance. The portfolio selection will only keep these if
they don't worsen jm/fg/ci/future metrics.
"""

src = open('Solution_20260531_v464_strong_cb_greedy.cpp').read()

# Add stronger CB-aware greedy portfolio entries
old_portfolio = """    run_greedy_cb_aware(m, 1, 1, 4, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    if(!huge_job){"""

new_portfolio = """    run_greedy_cb_aware(m, 1, 1, 4, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // Strong CB-aware: higher consolidation bonus
    run_greedy_cb_aware(m, 2, 1, 8, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    run_greedy_cb_aware(m, 2, 1, 12, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    run_greedy_cb_aware(m, 2, 1, 8, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    if(!huge_job){"""

assert old_portfolio in src, "Cannot find portfolio insertion point"
src = src.replace(old_portfolio, new_portfolio, 1)

open('Solution_20260531_v464_strong_cb_greedy.cpp', 'w').write(src)
print("Patch v464 applied successfully")
