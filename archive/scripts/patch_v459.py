#!/usr/bin/env python3
"""Patch v459: Sort flows by CT contribution in cbttskc_reduce.

Current: processes flows in index order (arbitrary).
New: sort flows by their CT contribution (highest first) so high-value moves get
first pick of target ports. This is a pure search-quality improvement.
"""

src = open('Solution_20260531_v459_ct_more_iters.cpp').read()

# Find the iteration loop in run_cbttskc_reduce
old_iter = """    for(int iter=0;iter<3;++iter){
        int improved=0;
        for(int fi=0;fi<fl_count;++fi){
            int sl=fl_sl[fi],dl=fl_dl[fi],px=fl_port[fi],ci=fl_src[fi];
            if(sl==dl||px<0) continue;"""

new_iter = """    for(int iter=0;iter<5;++iter){
        int improved=0;
        // Sort flows by CT contribution (highest first) for better greedy ordering
        static int ct_order[MAX_FLOWS];
        static int ct_val[MAX_FLOWS];
        int ct_cnt=0;
        for(int fi=0;fi<fl_count;++fi){
            int sl=fl_sl[fi],dl=fl_dl[fi],px=fl_port[fi];
            if(sl==dl||px<0) continue;
            int fo=global_out[sl][px]+ct_max_out[sl][px];
            int fi2=global_in[dl][px]+ct_max_in[dl][px];
            int ct_contrib=0;
            if(fo>g_r)ct_contrib+=(fo-g_r);
            if(fi2>g_r)ct_contrib+=(fi2-g_r);
            if(ct_contrib<=0) continue;
            ct_order[ct_cnt]=fi;
            ct_val[ct_cnt]=ct_contrib;
            ct_cnt++;
        }
        // Simple insertion sort by ct_val descending (ct_cnt typically small)
        for(int a=1;a<ct_cnt;++a){
            int key_o=ct_order[a],key_v=ct_val[a];
            int b=a-1;
            while(b>=0&&ct_val[b]<key_v){
                ct_order[b+1]=ct_order[b];ct_val[b+1]=ct_val[b];b--;
            }
            ct_order[b+1]=key_o;ct_val[b+1]=key_v;
        }
        for(int ci_idx=0;ci_idx<ct_cnt;++ci_idx){
            int fi=ct_order[ci_idx];
            int sl=fl_sl[fi],dl=fl_dl[fi],px=fl_port[fi],ci=fl_src[fi];
            if(sl==dl||px<0) continue;"""

assert old_iter in src, "Cannot find CT reduce iteration start"
src = src.replace(old_iter, new_iter, 1)

# Fix the closing brace - need to add one more closing brace for the new for loop
# The original loop ends with: if(!moved) break; }
# We don't need to change the end since we just replaced the inner for loop header

open('Solution_20260531_v459_ct_more_iters.cpp', 'w').write(src)
print("Patch v459 applied successfully")
