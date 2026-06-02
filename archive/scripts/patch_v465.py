#!/usr/bin/env python3
"""Patch v465: Top-2 portfolio selection with full post-processing on both.

Current: portfolio picks the single best greedy result, then runs post-processing once.
New: save the top-2 greedy results. Run full post-processing on the best one first.
Then restore the 2nd-best, run post-processing on it too, and keep whichever is better
after post-processing.

This avoids the problem where a greedy result that looks slightly worse in
future_sq/future_over actually produces a better final result after SA/PC/swaps.

Only do this for non-huge, non-time-tight jobs to avoid runtime issues.
"""

src = open('Solution_20260531_v465_top2_portfolio.cpp').read()

# We need to save a second-best state alongside the best state.
# Find where sv_out/sv_in/sv_port are declared (static arrays for saving best)
# and add sv2_* for second-best.

# Find the static declarations
old_sv_decl = "static short sv_port[MAX_FLOWS];"
assert old_sv_decl in src, "Cannot find sv_port declaration"

new_sv_decl = """static short sv_port[MAX_FLOWS];
static short sv2_out[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short sv2_in[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short sv2_port[MAX_FLOWS];"""

src = src.replace(old_sv_decl, new_sv_decl, 1)

# Modify TRY_STRATEGY to also track second-best
old_try = """    #define TRY_STRATEGY() do { \\
        EvalMetrics cur_eval=collect_metrics(m); \\
        if(cur_eval.jm<=g_r) any_jm_le_r=1; \\
        int take_strategy=0; \\
        if(first||better_metrics(cur_eval,best_eval)){ \\
            take_strategy=1; \\
        } else if(p32_gp_tiebreak && cur_uses_global_price && !best_uses_global_price && \\
                  cur_eval.score_jm==best_eval.score_jm && \\
                  cur_eval.score_fg==best_eval.score_fg && \\
                  cur_eval.ci==best_eval.ci && \\
                  total_cbtphsc_from_ports(fl_port,m) < total_cbtphsc_from_ports(sv_port,m)){ \\
            take_strategy=1; \\
        } \\
        if(take_strategy){ \\
            best_eval=cur_eval; first=0; \\
            best_uses_global_price=cur_uses_global_price; \\
            memcpy(sv_out, out_load, g_l*sizeof(out_load[0])); \\
            memcpy(sv_in, in_load, g_l*sizeof(in_load[0])); \\
            memcpy(sv_port, fl_port, fl_count*sizeof(short)); \\
        } \\
    } while(0)"""

new_try = """    EvalMetrics second_eval;
    int has_second=0;

    #define TRY_STRATEGY() do { \\
        EvalMetrics cur_eval=collect_metrics(m); \\
        if(cur_eval.jm<=g_r) any_jm_le_r=1; \\
        int take_strategy=0; \\
        if(first||better_metrics(cur_eval,best_eval)){ \\
            take_strategy=1; \\
        } else if(p32_gp_tiebreak && cur_uses_global_price && !best_uses_global_price && \\
                  cur_eval.score_jm==best_eval.score_jm && \\
                  cur_eval.score_fg==best_eval.score_fg && \\
                  cur_eval.ci==best_eval.ci && \\
                  total_cbtphsc_from_ports(fl_port,m) < total_cbtphsc_from_ports(sv_port,m)){ \\
            take_strategy=1; \\
        } \\
        if(take_strategy){ \\
            if(!first){ \\
                second_eval=best_eval; has_second=1; \\
                memcpy(sv2_out, sv_out, g_l*sizeof(out_load[0])); \\
                memcpy(sv2_in, sv_in, g_l*sizeof(in_load[0])); \\
                memcpy(sv2_port, sv_port, fl_count*sizeof(short)); \\
            } \\
            best_eval=cur_eval; first=0; \\
            best_uses_global_price=cur_uses_global_price; \\
            memcpy(sv_out, out_load, g_l*sizeof(out_load[0])); \\
            memcpy(sv_in, in_load, g_l*sizeof(in_load[0])); \\
            memcpy(sv_port, fl_port, fl_count*sizeof(short)); \\
        } else if(!first && !has_second){ \\
            second_eval=cur_eval; has_second=1; \\
            memcpy(sv2_out, out_load, g_l*sizeof(out_load[0])); \\
            memcpy(sv2_in, sv_in, g_l*sizeof(in_load[0])); \\
            memcpy(sv2_port, fl_port, fl_count*sizeof(short)); \\
        } else if(has_second && better_metrics(cur_eval,second_eval)){ \\
            second_eval=cur_eval; \\
            memcpy(sv2_out, out_load, g_l*sizeof(out_load[0])); \\
            memcpy(sv2_in, in_load, g_l*sizeof(in_load[0])); \\
            memcpy(sv2_port, fl_port, fl_count*sizeof(short)); \\
        } \\
    } while(0)"""

assert old_try in src, "Cannot find TRY_STRATEGY macro"
src = src.replace(old_try, new_try, 1)

# Now find where post-processing starts (after portfolio_done label, restore best)
# and add the top-2 comparison logic
old_restore = """    portfolio_done:
    // Restore best strategy
    memcpy(out_load, sv_out, g_l*sizeof(out_load[0]));
    memcpy(in_load, sv_in, g_l*sizeof(in_load[0]));
    memcpy(fl_port, sv_port, fl_count*sizeof(short));"""

assert old_restore in src, "Cannot find portfolio_done restore"

# After all post-processing and before global state update, add comparison with 2nd
# Find the global state update
old_global_update = """    // Update g_hist_max_jm with this job's final jm
    int final_jm = get_job_max(m);
    if(final_jm > g_hist_max_jm) g_hist_max_jm = final_jm;

    // Update global state - always use actual (post-processing) max"""

new_global_update = """    // Top-2 comparison: if we have a second-best and time allows, try it too
    if(has_second && !g_time_tight && !huge_job){
        // Save current (post-processed best) state
        EvalMetrics pp_best=collect_metrics(m);
        static short fin_out[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
        static short fin_in[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
        static short fin_port[MAX_FLOWS];
        memcpy(fin_out, out_load, g_l*sizeof(out_load[0]));
        memcpy(fin_in, in_load, g_l*sizeof(in_load[0]));
        memcpy(fin_port, fl_port, fl_count*sizeof(short));
        // Restore second-best and run abbreviated post-processing
        memcpy(out_load, sv2_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, sv2_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, sv2_port, fl_count*sizeof(short));
        run_port_consistency(m);
        run_neutral_swap(m);
        run_relaxed_swap(m);
        run_cross_dest_swap(m);
        EvalMetrics pp_second=collect_metrics(m);
        if(better_metrics(pp_second, pp_best)){
            // Second-best is actually better after post-processing!
        } else {
            // Restore the original best
            memcpy(out_load, fin_out, g_l*sizeof(out_load[0]));
            memcpy(in_load, fin_in, g_l*sizeof(in_load[0]));
            memcpy(fl_port, fin_port, fl_count*sizeof(short));
        }
    }

    // Update g_hist_max_jm with this job's final jm
    int final_jm = get_job_max(m);
    if(final_jm > g_hist_max_jm) g_hist_max_jm = final_jm;

    // Update global state - always use actual (post-processing) max"""

assert old_global_update in src, "Cannot find global update block"
src = src.replace(old_global_update, new_global_update, 1)

open('Solution_20260531_v465_top2_portfolio.cpp', 'w').write(src)
print("Patch v465 applied successfully")
