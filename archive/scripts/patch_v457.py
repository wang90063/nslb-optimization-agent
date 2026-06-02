#!/usr/bin/env python3
"""Patch v457: Bottleneck-aware greedy — only penalize the MM-bottleneck port heavily.

Insight: greedy penalizes ALL ports equally with global_out/global_in, but only the
single hottest (leaf,port) determines MM. If greedy knew which port is the bottleneck,
it could relax penalty on non-bottleneck ports, allowing better CB/CT choices without
hurting MM.

Implementation: Add as new portfolio strategy. Before greedy, compute current global
max (fg_threshold). During port selection, apply full global penalty only to ports
where global_out+local_max would exceed fg_threshold-margin; other ports get reduced
global weight.
"""

src = open('Solution_20260531_v457_bottleneck_aware.cpp').read()

# Find the run_greedy_ftrl function to insert before it
marker = "void run_greedy_ftrl(int m, int hardcap, int rev=0, int sc_div=2, int local_w=2){"
assert marker in src, f"Cannot find marker"

new_func = """// Bottleneck-aware greedy: reduce global penalty on non-bottleneck ports
void run_greedy_bottleneck(int m, int local_w, int global_w, int hardcap, int rev=0){
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
    // Compute current global fg (max over all leaf,port of global_out/in)
    int fg_now=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            if(global_out[leaf][pk]>fg_now)fg_now=global_out[leaf][pk];
            if(global_in[leaf][pk]>fg_now)fg_now=global_in[leaf][pk];
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
            int gv=go>gi?go:gi;
            // Reduce global weight for non-bottleneck ports
            int eff_gw=global_w;
            if(gv+local_max < fg_now) eff_gw=0; // far from bottleneck: no global penalty
            int cost=local_max*local_w+gv*eff_gw;
            if(exceeds) cost+=10000;
            // Future tie-break
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

# Add portfolio entries
old_portfolio = """    run_greedy_cb_aware(m, 1, 1, 4, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    if(!huge_job){"""

new_portfolio = """    run_greedy_cb_aware(m, 1, 1, 4, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // Bottleneck-aware: relax global penalty on non-bottleneck ports
    run_greedy_bottleneck(m, 2, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    run_greedy_bottleneck(m, 2, 1, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    if(!huge_job){"""

assert old_portfolio in src, "Cannot find portfolio insertion point"
src = src.replace(old_portfolio, new_portfolio, 1)

open('Solution_20260531_v457_bottleneck_aware.cpp', 'w').write(src)
print("Patch v457 applied successfully")
