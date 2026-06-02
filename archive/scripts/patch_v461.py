#!/usr/bin/env python3
"""Patch v461: Popcount-sorted greedy order as new portfolio strategy.

Flows with more active phases (higher popcount of pmask) have more impact on load
distribution. Allocating them first lets greedy make better-informed decisions for
the high-impact flows. Add as portfolio strategy (sorted by popcount desc).
"""

src = open('Solution_20260531_v461_popcount_order.cpp').read()

# We need to add a new ordering mode to run_greedy. Currently rev=0 (forward),
# rev=1 (reverse), rev>=2 (random shuffle). We'll add rev=4 for popcount-sorted.
# Simpler approach: add a new function that pre-sorts fl_order by popcount then calls greedy with rev=2-like logic.

# Find run_greedy function to understand its signature
# void run_greedy(int m, int local_w, int global_w, int hardcap, int rev=0){

# Instead of modifying run_greedy, add a pre-sort step before calling it with rev>=2
# We'll sort fl_order by popcount descending, then call run_greedy with rev=2 which uses fl_order

# Add portfolio entries that pre-sort fl_order by popcount then use run_greedy with rev=2
old_portfolio = """    run_greedy_cb_aware(m, 1, 1, 4, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    if(!huge_job){"""

new_portfolio = """    run_greedy_cb_aware(m, 1, 1, 4, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // Popcount-sorted order: high-impact flows (many active phases) first
    {
        for(int i=0;i<fl_count;++i) fl_order[i]=i;
        // Sort by popcount descending (insertion sort, stable)
        for(int a=1;a<fl_count;++a){
            int key=fl_order[a];
            int kpc=__builtin_popcount(fl_pmask[key]);
            int b=a-1;
            while(b>=0&&__builtin_popcount(fl_pmask[fl_order[b]])<kpc){
                fl_order[b+1]=fl_order[b];b--;
            }
            fl_order[b+1]=key;
        }
        run_greedy(m, 2, 1, 1, 2);
        run_swap(m);
        run_jm_repair(m);
        TRY_STRATEGY();
    }

    if(!huge_job){"""

assert old_portfolio in src, "Cannot find portfolio insertion point"
src = src.replace(old_portfolio, new_portfolio, 1)

open('Solution_20260531_v461_popcount_order.cpp', 'w').write(src)
print("Patch v461 applied successfully")
