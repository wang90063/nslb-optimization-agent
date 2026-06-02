#!/usr/bin/env python3
"""Patch v462: Add CB as final tiebreak in portfolio selection (better_metrics)."""

src = open('Solution_20260531_v462_portfolio_cb_tie.cpp').read()

# Add CB to EvalMetrics struct (actual field order in file)
old_struct = """struct EvalMetrics{
    int score_jm;
    int score_fg;
    int jm;
    int fg;
    int ci;
    int future_over;
    long long future_sq;
};"""

new_struct = """struct EvalMetrics{
    int score_jm;
    int score_fg;
    int jm;
    int fg;
    int ci;
    int future_over;
    long long future_sq;
    int cb;
};"""

assert old_struct in src, "Cannot find EvalMetrics struct"
src = src.replace(old_struct, new_struct, 1)

# Add CB init in collect_metrics
old_collect_end = """    em.score_jm=em.jm>g_r?em.jm:g_r;
    if(g_hist_max_jm>em.score_jm) em.score_jm=g_hist_max_jm;
    em.score_fg=em.fg>g_r?em.fg:g_r;
    return em;
}"""

new_collect_end = """    em.score_jm=em.jm>g_r?em.jm:g_r;
    if(g_hist_max_jm>em.score_jm) em.score_jm=g_hist_max_jm;
    em.score_fg=em.fg>g_r?em.fg:g_r;
    em.cb=0;
    return em;
}"""

assert old_collect_end in src, "Cannot find collect_metrics end"
src = src.replace(old_collect_end, new_collect_end, 1)

# Add CB as final tiebreak in better_metrics
old_better = """    if(a.jm!=b.jm) return a.jm<b.jm;
    if(a.fg!=b.fg) return a.fg<b.fg;
    return 0;
}"""

new_better = """    if(a.jm!=b.jm) return a.jm<b.jm;
    if(a.fg!=b.fg) return a.fg<b.fg;
    if(a.cb!=b.cb) return a.cb<b.cb;
    return 0;
}"""

assert old_better in src, "Cannot find better_metrics end"
src = src.replace(old_better, new_better, 1)

# In TRY_STRATEGY, compute CB before comparison
old_try = """    #define TRY_STRATEGY() do { \\
        EvalMetrics cur_eval=collect_metrics(m); \\
        if(cur_eval.jm<=g_r) any_jm_le_r=1; \\"""

new_try = """    #define TRY_STRATEGY() do { \\
        EvalMetrics cur_eval=collect_metrics(m); \\
        cur_eval.cb=total_cbtphsc_from_ports(fl_port,m); \\
        if(cur_eval.jm<=g_r) any_jm_le_r=1; \\"""

assert old_try in src, "Cannot find TRY_STRATEGY macro"
src = src.replace(old_try, new_try, 1)

open('Solution_20260531_v462_portfolio_cb_tie.cpp', 'w').write(src)
print("Patch v462 applied successfully")
