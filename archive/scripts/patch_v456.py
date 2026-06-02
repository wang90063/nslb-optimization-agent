#!/usr/bin/env python3
"""Patch v456: Greedy cost uses go+gi (sum) instead of max(go,gi).

Rationale: max(go,gi) loses information. A port with go=10,gi=2 and go=6,gi=6
both score 10 under max, but the latter distributes load more evenly across leafs.
Sum distinguishes them (12 vs 12 — same here, but in general sum provides smoother
gradient). More importantly, sum penalizes ports that are hot on BOTH sides.

We add this as a NEW portfolio strategy (not replacing existing ones) to test
whether sum-based cost finds better solutions on some jobs.
"""

import re

src = open('Solution_20260531_v456_greedy_sum_global.cpp').read()

# Add a new greedy variant: run_greedy_sum that uses go+gi instead of max(go,gi)
# Insert it right after run_greedy_cb_aware function definition

# Find the end of run_greedy_cb_aware
marker = "void run_greedy_ftrl(int m, int hardcap, int rev=0, int sc_div=2, int local_w=2){"
assert marker in src, f"Cannot find marker: {marker}"

new_func = """// Greedy with sum(go,gi) cost instead of max(go,gi)
void run_greedy_sum(int m, int local_w, int global_w, int hardcap, int rev=0){
    memset(out_load,0,g_l*sizeof(out_load[0]));
    memset(in_load,0,g_l*sizeof(in_load[0]));
    if(rev>=2){
        unsigned int seed=rev*2654435761u;
        for(int a=fl_count-1;a>0;--a){
            seed=seed*1664525u+1013904223u;
            int b=seed%(a+1);
            int t=fl_order[a];fl_order[a]=fl_order[b];fl_order[b]=t;
        }
    }
    for(int ii=0;ii<fl_count;++ii){
        int i;
        if(rev==0) i=ii;
        else if(rev==1) i=fl_count-1-ii;
        else i=fl_order[ii];
        int sl=fl_sl[i],dl=fl_dl[i];
        if(sl==dl){fl_port[i]=-1;continue;}
        unsigned int mask=fl_pmask[i];
        int bp=0,bc=0x7fffffff;
        int bt_over=0x7fffffff;
        long long bt_sq=0x7fffffffffffffffLL;
        for(int pk=0;pk<g_p;++pk){
            int local_max=0;
            int exceeds=0;
            int mo=0,mi=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                int v=o>iv?o:iv;if(v>local_max)local_max=v;
                if(hardcap&&(o>g_r||iv>g_r)) exceeds=1;
                if(o>mo)mo=o;
                if(iv>mi)mi=iv;
                m2&=m2-1;
            }
            int go=global_out[sl][pk],gi=global_in[dl][pk];
            int gv=go+gi;  // SUM instead of MAX
            int cost=local_max*local_w+gv*global_w;
            if(exceeds) cost+=10000;
            // Future tie-break using sum-based sq
            for(int ph=0;ph<m;++ph){
                int o=out_load[sl][pk][ph];if(o>mo)mo=o;
                int iv=in_load[dl][pk][ph];if(iv>mi)mi=iv;
            }
            int fo=go+mo,fi=gi+mi;
            int cand_over=0;
            if(fo>g_r) cand_over+=(fo-g_r);
            if(fi>g_r) cand_over+=(fi-g_r);
            long long cand_sq=(long long)fo*fo+(long long)fi*fi;
            if(cost<bc||(cost==bc&&cand_over<bt_over)||(cost==bc&&cand_over==bt_over&&cand_sq<bt_sq)){
                bc=cost;bp=pk;bt_over=cand_over;bt_sq=cand_sq;
            }
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
}

"""

src = src.replace(marker, new_func + marker, 1)

# Add portfolio entries for the new greedy_sum strategy
# Insert after the last CB-aware strategy (before if(!huge_job))
old_portfolio = """    run_greedy_cb_aware(m, 1, 1, 4, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    if(!huge_job){"""

new_portfolio = """    run_greedy_cb_aware(m, 1, 1, 4, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // Sum-based global cost strategies
    run_greedy_sum(m, 2, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    run_greedy_sum(m, 2, 1, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    if(!huge_job){"""

assert old_portfolio in src, "Cannot find portfolio insertion point"
src = src.replace(old_portfolio, new_portfolio, 1)

open('Solution_20260531_v456_greedy_sum_global.cpp', 'w').write(src)
print("Patch v456 applied successfully")
