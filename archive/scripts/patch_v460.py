#!/usr/bin/env python3
"""Patch v460: CB tiebreak in cross_dest_swap's soft_pks selection.

Current: when multiple ports are "near-equivalent" in CI/local/future metrics,
cross_dest randomly picks one. New: pick the one that best improves card
consolidation (CB). This is a pure tiebreak — doesn't change which moves are
accepted, only which near-equivalent target is chosen.
"""

src = open('Solution_20260531_v460_crossdest_cb_tie.cpp').read()

# Replace the random selection in soft_pks with CB-aware selection
old_soft = """    if(soft_cnt>1){
        rng=rng*1664525u+1013904223u;
        best_pk=soft_pks[(rng>>16)%soft_cnt];
        if(best_delta_out) *best_delta_out=cand_delta[best_pk];
    }
    return best_pk;
}"""

new_soft = """    if(soft_cnt>1){
        // CB tiebreak: pick the soft port that best improves card consolidation
        int ci=fl_src[fi];
        int best_cb_net=-999999;
        int before_cbt=card_cbtphsc(ci,m);
        for(int si=0;si<soft_cnt;++si){
            int pk=soft_pks[si];
            // Simulate move: update cppc/cpm temporarily
            unsigned int mk=mask;
            while(mk){int ph=__builtin_ctz(mk);
                cppc[ci][ph][cp]--;if(!cppc[ci][ph][cp])cpm[ci][ph]&=~(1u<<cp);
                cppc[ci][ph][pk]++;cpm[ci][ph]|=(1u<<pk);mk&=mk-1;}
            int after_cbt=card_cbtphsc(ci,m);
            int net=before_cbt-after_cbt;
            mk=mask;
            while(mk){int ph=__builtin_ctz(mk);
                cppc[ci][ph][pk]--;if(!cppc[ci][ph][pk])cpm[ci][ph]&=~(1u<<pk);
                cppc[ci][ph][cp]++;cpm[ci][ph]|=(1u<<cp);mk&=mk-1;}
            if(net>best_cb_net){best_cb_net=net;best_pk=pk;}
        }
        if(best_delta_out) *best_delta_out=cand_delta[best_pk];
    }
    return best_pk;
}"""

assert old_soft in src, "Cannot find soft_pks random selection"
src = src.replace(old_soft, new_soft, 1)

open('Solution_20260531_v460_crossdest_cb_tie.cpp', 'w').write(src)
print("Patch v460 applied successfully")
