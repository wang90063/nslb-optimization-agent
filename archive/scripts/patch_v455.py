#!/usr/bin/env python3
"""Patch v455: Relax ct_max ceiling in cbttskc_reduce with global-aware condition.

Instead of hard-blocking any move that would increase a target port's max-phase-load,
allow it if global_out[sl][py] + (ct_max+1) <= current_fg (i.e., won't become new MM bottleneck).
"""

import re

src = open('Solution_20260531_v455_ct_ceiling_relax.cpp').read()

# Find the ct_max check in run_cbttskc_reduce:
# Original (lines 2100-2103):
#     while(m3){int ph=__builtin_ctz(m3);
#         if(out_load[sl][py][ph]+1>ct_max_out[sl][py]){ok=0;break;}
#         if(in_load[dl][py][ph]+1>ct_max_in[dl][py]){ok=0;break;}
#         m3&=m3-1;}
#     if(!ok) continue;
#
# New: compute current fg at start of function, then allow +1 if it won't exceed fg

# Step 1: Add fg computation at the start of run_cbttskc_reduce, after ct_max init
old_after_ctmax = """    for(int iter=0;iter<3;++iter){
        int improved=0;"""

new_after_ctmax = """    // Compute current fg (global max) for relaxed ceiling check
    int ct_cur_fg=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int fo=global_out[leaf][pk]+ct_max_out[leaf][pk];
            int fi=global_in[leaf][pk]+ct_max_in[leaf][pk];
            if(fo>ct_cur_fg)ct_cur_fg=fo;
            if(fi>ct_cur_fg)ct_cur_fg=fi;
        }
    for(int iter=0;iter<3;++iter){
        int improved=0;"""

assert old_after_ctmax in src, "Cannot find iter loop start"
src = src.replace(old_after_ctmax, new_after_ctmax, 1)

# Step 2: Replace the hard ct_max check with global-aware relaxed check
old_check = """                while(m3){int ph=__builtin_ctz(m3);
                    if(out_load[sl][py][ph]+1>ct_max_out[sl][py]){ok=0;break;}
                    if(in_load[dl][py][ph]+1>ct_max_in[dl][py]){ok=0;break;}
                    m3&=m3-1;}
                if(!ok) continue;"""

new_check = """                int new_max_out_py=ct_max_out[sl][py];
                int new_max_in_py=ct_max_in[dl][py];
                while(m3){int ph=__builtin_ctz(m3);
                    int ov=out_load[sl][py][ph]+1;
                    int iv=in_load[dl][py][ph]+1;
                    if(ov>new_max_out_py)new_max_out_py=ov;
                    if(iv>new_max_in_py)new_max_in_py=iv;
                    m3&=m3-1;}
                if(global_out[sl][py]+new_max_out_py>ct_cur_fg){ok=0;}
                if(global_in[dl][py]+new_max_in_py>ct_cur_fg){ok=0;}
                if(ok==0) continue;"""

assert old_check in src, "Cannot find ct_max check block"
src = src.replace(old_check, new_check, 1)

open('Solution_20260531_v455_ct_ceiling_relax.cpp', 'w').write(src)
print("Patch v455 applied successfully")
