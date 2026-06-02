#!/usr/bin/env python3
"""Patch v454: Use actual (post-CT-reduce) max for global_out update.
Currently when ct_pass_ran=1, global_out uses pre_ct_mo (conservative).
Change to use the actual post-processing max, which matches what the
scorer sees and gives future jobs more accurate global information.
"""
import sys

src = "/Users/wangran/Desktop/code/submission-test/Solution_20260531_v454_actual_global_out.cpp"
with open(src, 'r') as f:
    code = f.read()

# Replace the global_out update logic
old_update = """    // Update global state - use pre-pass max_phase if Cbttskc pass ran
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int inc_o=0,inc_i=0;
            if(ct_pass_ran){
                global_out[leaf][pk]+=pre_ct_mo[leaf][pk];
                global_in[leaf][pk]+=pre_ct_mi[leaf][pk];
                inc_o=pre_ct_mo[leaf][pk];
                inc_i=pre_ct_mi[leaf][pk];
            } else {
                int mo=0,mi=0;
                for(int ph=0;ph<m;++ph){if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];}
                global_out[leaf][pk]+=mo;global_in[leaf][pk]+=mi;
                inc_o=mo;
                inc_i=mi;
            }
            if(inc_o>g_r) global_price_out[leaf][pk]+=inc_o-g_r;
            if(inc_i>g_r) global_price_in[leaf][pk]+=inc_i-g_r;
            if(inc_o>0) global_price_src[leaf][pk]+=inc_o;
            if(inc_i>0) global_price_dst[leaf][pk]+=inc_i;
        }"""

new_update = """    // Update global state - always use actual (post-processing) max
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int mo=0,mi=0;
            for(int ph=0;ph<m;++ph){if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];}
            global_out[leaf][pk]+=mo;global_in[leaf][pk]+=mi;
            if(mo>g_r) global_price_out[leaf][pk]+=mo-g_r;
            if(mi>g_r) global_price_in[leaf][pk]+=mi-g_r;
            if(mo>0) global_price_src[leaf][pk]+=mo;
            if(mi>0) global_price_dst[leaf][pk]+=mi;
        }"""

pos = code.find(old_update)
if pos < 0:
    print("ERROR: global_out update not found")
    sys.exit(1)

code = code[:pos] + new_update + code[pos+len(old_update):]

with open(src, 'w') as f:
    f.write(code)

print("v454 patch applied successfully")
