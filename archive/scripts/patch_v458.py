#!/usr/bin/env python3
"""Patch v458: Add a second CT reduce pass after SA.

SA changes load distribution, potentially making previously-infeasible CT-reducing
moves feasible. Add a guarded CT reduce pass after the SA+swap block.
"""

src = open('Solution_20260531_v458_post_sa_ct.cpp').read()

# Find the SA swap block end and global state update
old_block = """    // Update g_hist_max_jm with this job's final jm
    int final_jm = get_job_max(m);
    if(final_jm > g_hist_max_jm) g_hist_max_jm = final_jm;"""

new_block = """    // Post-SA CT reduce: SA may have changed load distribution,
    // making previously-infeasible CT moves feasible
    if(!g_time_tight){
        memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
        memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
        memcpy(bk_port, fl_port, fl_count*sizeof(short));
        EvalMetrics ct2_base=collect_metrics(m);
        run_cbttskc_reduce(m);
        EvalMetrics ct2_after=collect_metrics(m);
        if(ct2_after.fg>ct2_base.fg||(ct2_after.fg==ct2_base.fg&&ct2_after.jm>ct2_base.jm)){
            memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
            memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
            memcpy(fl_port, bk_port, fl_count*sizeof(short));
        } else {
            run_neutral_swap(m);
            run_relaxed_swap(m);
        }
    }

    // Update g_hist_max_jm with this job's final jm
    int final_jm = get_job_max(m);
    if(final_jm > g_hist_max_jm) g_hist_max_jm = final_jm;"""

assert old_block in src, "Cannot find insertion point"
src = src.replace(old_block, new_block, 1)

open('Solution_20260531_v458_post_sa_ct.cpp', 'w').write(src)
print("Patch v458 applied successfully")
