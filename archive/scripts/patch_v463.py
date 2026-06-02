#!/usr/bin/env python3
"""Patch v463: SA with CT-focused search list.

Current SA only searches flows from cards with CB>0. But CT improvement needs
moving flows from high-CT ports regardless of their card's CB status.

Add CT contribution to SA focused list: include flows on ports where
global_out+max > r (i.e., ports contributing to CT). Also add CT term to SA objective.
"""

src = open('Solution_20260531_v463_sa_ct_focused.cpp').read()

# Find the SA focused list construction
old_focus = """    // Build focused list: flows from cards with CB > 0
    static int sa_focus[MAX_FLOWS];
    int sa_focus_cnt=0;
    {
        static int card_cb_done[MAX_CARDS];
        static int card_cb_val[MAX_CARDS];
        static int cb_cards[MAX_CARDS];
        int cb_card_cnt=0;
        for(int i=0;i<fl_count;++i){
            if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
            int c=fl_src[i];
            if(card_cb_done[c]!=g_job_idx+1){
                card_cb_done[c]=g_job_idx+1;
                card_cb_val[c]=card_cbtphsc(c,m);
                if(card_cb_val[c]>0) cb_cards[cb_card_cnt++]=c;
            }
            if(card_cb_val[c]>0) sa_focus[sa_focus_cnt++]=i;
        }
    }"""

new_focus = """    // Build focused list: flows from cards with CB > 0 OR on high-CT ports
    static int sa_focus[MAX_FLOWS];
    int sa_focus_cnt=0;
    {
        static int card_cb_done[MAX_CARDS];
        static int card_cb_val[MAX_CARDS];
        static int cb_cards[MAX_CARDS];
        int cb_card_cnt=0;
        // Mark ports with CT contribution
        static char port_has_ct[MAX_LEAFS][MAX_PORTS];
        for(int leaf=0;leaf<g_l;++leaf)
            for(int pk=0;pk<g_p;++pk){
                int fo=global_out[leaf][pk]+sa_max_out[leaf][pk];
                int fi=global_in[leaf][pk]+sa_max_in[leaf][pk];
                port_has_ct[leaf][pk]=((fo>g_r)||(fi>g_r))?1:0;
            }
        for(int i=0;i<fl_count;++i){
            if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
            int c=fl_src[i];
            int p=fl_port[i];
            if(card_cb_done[c]!=g_job_idx+1){
                card_cb_done[c]=g_job_idx+1;
                card_cb_val[c]=card_cbtphsc(c,m);
                if(card_cb_val[c]>0) cb_cards[cb_card_cnt++]=c;
            }
            int include=(card_cb_val[c]>0)||port_has_ct[fl_sl[i]][p]||port_has_ct[fl_dl[i]][p];
            if(include) sa_focus[sa_focus_cnt++]=i;
        }
    }"""

assert old_focus in src, "Cannot find SA focused list construction"
src = src.replace(old_focus, new_focus, 1)

# Add CT term to SA objective: obj_delta = 12*ci_delta + 5*cbt_delta + 3*ct_delta
# Find the objective computation
old_obj = """        int obj_delta=12*ci_delta+5*cbt_delta;
        int accept=0;
        if(obj_delta<=0) accept=1;"""

# We need to compute ct_delta: change in Cbttskc contribution for this flow's ports
new_obj = """        // CT delta: change in max-phase contribution to Cbttskc
        int ct_delta=0;
        {
            // Source port px: if removing flow reduces max, CT may decrease
            short old_mo_px=sa_max_out[sl][px],old_mi_px=sa_max_in[dl][px];
            short new_mo_px=0,new_mi_px=0;
            for(int ph2=0;ph2<m;++ph2){
                int ov=out_load[sl][px][ph2]-((mask>>ph2)&1u);
                int iv=in_load[dl][px][ph2]-((mask>>ph2)&1u);
                if(ov>(int)new_mo_px)new_mo_px=(short)ov;
                if(iv>(int)new_mi_px)new_mi_px=(short)iv;
            }
            int old_ct_px=0,new_ct_px=0;
            int fo_old=global_out[sl][px]+old_mo_px;
            int fo_new=global_out[sl][px]+new_mo_px;
            if(fo_old>g_r)old_ct_px+=(fo_old-g_r);
            if(fo_new>g_r)new_ct_px+=(fo_new-g_r);
            int fi_old=global_in[dl][px]+old_mi_px;
            int fi_new=global_in[dl][px]+new_mi_px;
            if(fi_old>g_r)old_ct_px+=(fi_old-g_r);
            if(fi_new>g_r)new_ct_px+=(fi_new-g_r);
            ct_delta+=(new_ct_px-old_ct_px);
            // Dest port py: adding flow may increase max, CT may increase
            short old_mo_py=sa_max_out[sl][py],old_mi_py=sa_max_in[dl][py];
            short new_mo_py=old_mo_py,new_mi_py=old_mi_py;
            unsigned int m3=mask;
            while(m3){int ph2=__builtin_ctz(m3);
                int ov=out_load[sl][py][ph2]+1;
                int iv=in_load[dl][py][ph2]+1;
                if(ov>(int)new_mo_py)new_mo_py=(short)ov;
                if(iv>(int)new_mi_py)new_mi_py=(short)iv;
                m3&=m3-1;}
            int old_ct_py=0,new_ct_py=0;
            fo_old=global_out[sl][py]+old_mo_py;
            fo_new=global_out[sl][py]+new_mo_py;
            if(fo_old>g_r)old_ct_py+=(fo_old-g_r);
            if(fo_new>g_r)new_ct_py+=(fo_new-g_r);
            fi_old=global_in[dl][py]+old_mi_py;
            fi_new=global_in[dl][py]+new_mi_py;
            if(fi_old>g_r)old_ct_py+=(fi_old-g_r);
            if(fi_new>g_r)new_ct_py+=(fi_new-g_r);
            ct_delta+=(new_ct_py-old_ct_py);
        }
        int obj_delta=12*ci_delta+5*cbt_delta+3*ct_delta;
        int accept=0;
        if(obj_delta<=0) accept=1;"""

assert old_obj in src, "Cannot find SA objective"
src = src.replace(old_obj, new_obj, 1)

open('Solution_20260531_v463_sa_ct_focused.cpp', 'w').write(src)
print("Patch v463 applied successfully")
