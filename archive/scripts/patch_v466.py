#!/usr/bin/env python3
"""Patch v466: Relaxed portfolio selection — when future_sq difference is tiny,
allow CB to break the tie.

Current better_metrics is strictly lexicographic: score_jm > score_fg > ci >
future_over > future_sq > jm > fg. This means a strategy with future_sq
differing by 1 (negligible MM impact) will always beat one with much better CB.

New: when score_jm/score_fg/ci/future_over are equal and future_sq difference
is within a small threshold, compare CB instead.
"""

src = open('Solution_20260531_v466_relaxed_portfolio.cpp').read()

# Replace better_metrics to add CB-aware relaxation
old_better = """inline int better_metrics(const EvalMetrics &a,const EvalMetrics &b){
    if(a.score_jm!=b.score_jm) return a.score_jm<b.score_jm;
    if(a.score_fg!=b.score_fg) return a.score_fg<b.score_fg;
    if(a.ci!=b.ci) return a.ci<b.ci;
    if(a.future_over!=b.future_over) return a.future_over<b.future_over;
    if(a.future_sq!=b.future_sq) return a.future_sq<b.future_sq;
    if(a.jm!=b.jm) return a.jm<b.jm;
    if(a.fg!=b.fg) return a.fg<b.fg;
    return 0;
}"""

new_better = """inline int better_metrics(const EvalMetrics &a,const EvalMetrics &b){
    if(a.score_jm!=b.score_jm) return a.score_jm<b.score_jm;
    if(a.score_fg!=b.score_fg) return a.score_fg<b.score_fg;
    if(a.ci!=b.ci) return a.ci<b.ci;
    if(a.future_over!=b.future_over) return a.future_over<b.future_over;
    if(a.future_sq!=b.future_sq) return a.future_sq<b.future_sq;
    if(a.jm!=b.jm) return a.jm<b.jm;
    if(a.fg!=b.fg) return a.fg<b.fg;
    return 0;
}

// Relaxed comparison: when primary metrics are equal and future_sq is close,
// prefer lower CB. Used only in portfolio selection (not in post-processing gates).
static int g_relaxed_cb_a=0, g_relaxed_cb_b=0;
inline int better_metrics_relaxed(const EvalMetrics &a,const EvalMetrics &b){
    if(a.score_jm!=b.score_jm) return a.score_jm<b.score_jm;
    if(a.score_fg!=b.score_fg) return a.score_fg<b.score_fg;
    if(a.ci!=b.ci) return a.ci<b.ci;
    if(a.future_over!=b.future_over) return a.future_over<b.future_over;
    // Relaxed future_sq: if within 0.5% of larger value, treat as equal
    long long diff=a.future_sq-b.future_sq;
    long long threshold=b.future_sq/200; // 0.5%
    if(threshold<4) threshold=4;
    if(diff<-threshold) return 1;
    if(diff>threshold) return 0;
    // future_sq is "close enough" — use CB as tiebreak
    if(g_relaxed_cb_a!=g_relaxed_cb_b) return g_relaxed_cb_a<g_relaxed_cb_b;
    if(a.future_sq!=b.future_sq) return a.future_sq<b.future_sq;
    if(a.jm!=b.jm) return a.jm<b.jm;
    if(a.fg!=b.fg) return a.fg<b.fg;
    return 0;
}"""

assert old_better in src, "Cannot find better_metrics"
src = src.replace(old_better, new_better, 1)

# Modify TRY_STRATEGY to use relaxed comparison
old_try_cmp = """        if(first||better_metrics(cur_eval,best_eval)){ \\
            take_strategy=1; \\"""

new_try_cmp = """        g_relaxed_cb_a=total_cbtphsc_from_ports(fl_port,m); \\
        g_relaxed_cb_b=first?0x7fffffff:total_cbtphsc_from_ports(sv_port,m); \\
        if(first||better_metrics_relaxed(cur_eval,best_eval)){ \\
            take_strategy=1; \\"""

assert old_try_cmp in src, "Cannot find TRY_STRATEGY comparison"
src = src.replace(old_try_cmp, new_try_cmp, 1)

open('Solution_20260531_v466_relaxed_portfolio.cpp', 'w').write(src)
print("Patch v466 applied successfully")
