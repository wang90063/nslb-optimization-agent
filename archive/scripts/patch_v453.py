#!/usr/bin/env python3
"""Patch v453: Card-batch SA neighborhood.
Instead of moving single flows, move ALL flows from the same card
on the same port to another port simultaneously.
Advantages:
- Directly reduces CB (consolidates card onto fewer ports)
- Removing multiple flows from source port drops max-phase-load more,
  potentially making the move feasible even when single-flow moves aren't
"""
import sys

src = "/Users/wangran/Desktop/code/submission-test/Solution_20260531_v453_card_batch_sa.cpp"
with open(src, 'r') as f:
    code = f.read()

# Insert run_sa_card_batch before run_sa_composite
marker = "void run_sa_composite(int m){"
pos = code.find(marker)
if pos < 0:
    print("ERROR: marker not found")
    sys.exit(1)

new_func = '''void run_sa_card_batch(int m){
    if(fl_count<10) return;
    clock_t sa_start=clock();
    double sa_budget=0.015;
    static short cb_max_out[MAX_LEAFS][MAX_PORTS];
    static short cb_max_in[MAX_LEAFS][MAX_PORTS];
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            short mo=0,mi=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
            }
            cb_max_out[leaf][pk]=mo;cb_max_in[leaf][pk]=mi;
        }
    // Build card-port index: for each (card, port), list of flow indices
    static int cp_flows[MAX_CARDS][MAX_PORTS][64];
    static int cp_cnt[MAX_CARDS][MAX_PORTS];
    memset(cp_cnt,0,sizeof(cp_cnt));
    int max_card=0;
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
        int c=fl_src[i],p=fl_port[i];
        if(c>max_card) max_card=c;
        if(cp_cnt[c][p]<64) cp_flows[c][p][cp_cnt[c][p]++]=i;
    }
    memset(cpm,0,sizeof(cpm));memset(cppc,0,sizeof(cppc));
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
        int c=fl_src[i],p=fl_port[i];
        unsigned int mk=fl_pmask[i];
        while(mk){int ph=__builtin_ctz(mk);cppc[c][ph][p]++;cpm[c][ph]|=(1u<<p);mk&=mk-1;}
    }
    // Build list of (card, port) pairs with CB contribution
    static int cb_pairs[MAX_CARDS*MAX_PORTS][2];
    int cb_pair_cnt=0;
    for(int c=0;c<=max_card;++c)
        for(int p=0;p<g_p;++p)
            if(cp_cnt[c][p]>0 && card_cbtphsc(c,m)>0)
                if(cb_pair_cnt<MAX_CARDS*MAX_PORTS)
                    {cb_pairs[cb_pair_cnt][0]=c;cb_pairs[cb_pair_cnt][1]=p;cb_pair_cnt++;}
    if(cb_pair_cnt==0) return;
    unsigned int rng=fl_count*1013904223u+g_job_idx*2654435761u;
    for(int iter=0;;++iter){
        if((iter&0x3F)==0){
            double elapsed=(double)(clock()-sa_start)/CLOCKS_PER_SEC;
            if(elapsed>=sa_budget) break;
        }
        rng=rng*1664525u+1013904223u;
        int pi=rng%cb_pair_cnt;
        int card=cb_pairs[pi][0],px=cb_pairs[pi][1];
        int cnt=cp_cnt[card][px];
        if(cnt==0) continue;
        // All flows from this card on port px must have same source leaf
        int sl=fl_sl[cp_flows[card][px][0]];
        rng=rng*1664525u+1013904223u;
        int py=rng%(g_p-1); if(py>=px)py++;
        // Check feasibility: can all flows move from px to py within sa_max?
        int ok=1;
        // First compute the combined phase mask and check out_load on source leaf
        for(int fi_idx=0;fi_idx<cnt&&ok;++fi_idx){
            int fi=cp_flows[card][px][fi_idx];
            int dl=fl_dl[fi];
            unsigned int m2=fl_pmask[fi];
            while(m2){int ph=__builtin_ctz(m2);
                if(out_load[sl][py][ph]+1>cb_max_out[sl][py]){ok=0;break;}
                if(in_load[dl][py][ph]+1>cb_max_in[dl][py]){ok=0;break;}
                m2&=m2-1;}
        }
        if(!ok) continue;
        // Compute CB delta
        int before_cb=card_cbtphsc(card,m);
        // Simulate move in cppc/cpm
        for(int fi_idx=0;fi_idx<cnt;++fi_idx){
            int fi=cp_flows[card][px][fi_idx];
            unsigned int mk=fl_pmask[fi];
            while(mk){int ph=__builtin_ctz(mk);
                cppc[card][ph][px]--;if(!cppc[card][ph][px])cpm[card][ph]&=~(1u<<px);
                cppc[card][ph][py]++;cpm[card][ph]|=(1u<<py);mk&=mk-1;}
        }
        int after_cb=card_cbtphsc(card,m);
        int cb_delta=after_cb-before_cb;
        if(cb_delta>=0){
            // Undo
            for(int fi_idx=0;fi_idx<cnt;++fi_idx){
                int fi=cp_flows[card][px][fi_idx];
                unsigned int mk=fl_pmask[fi];
                while(mk){int ph=__builtin_ctz(mk);
                    cppc[card][ph][py]--;if(!cppc[card][ph][py])cpm[card][ph]&=~(1u<<py);
                    cppc[card][ph][px]++;cpm[card][ph]|=(1u<<px);mk&=mk-1;}
            }
            continue;
        }
        // Accept: update loads
        for(int fi_idx=0;fi_idx<cnt;++fi_idx){
            int fi=cp_flows[card][px][fi_idx];
            int dl=fl_dl[fi];
            unsigned int mk=fl_pmask[fi];
            while(mk){int ph=__builtin_ctz(mk);
                out_load[sl][px][ph]--;out_load[sl][py][ph]++;
                in_load[dl][px][ph]--;in_load[dl][py][ph]++;mk&=mk-1;}
            fl_port[fi]=(short)py;
        }
        // Update cb_max (may have decreased on px)
        short nmo=0,nmi=0;
        for(int ph=0;ph<m;++ph){
            if(out_load[sl][px][ph]>nmo)nmo=out_load[sl][px][ph];}
        cb_max_out[sl][px]=nmo;
        // Move flows from cp_flows[card][px] to cp_flows[card][py]
        for(int fi_idx=0;fi_idx<cnt;++fi_idx){
            int fi=cp_flows[card][px][fi_idx];
            if(cp_cnt[card][py]<64) cp_flows[card][py][cp_cnt[card][py]++]=fi;
        }
        cp_cnt[card][px]=0;
    }
}

'''

code = code[:pos] + new_func + code[pos:]

# Insert call before SA 3-pass
sa_marker = "// Two-pass SA: split budget, CB recovery between passes"
pos2 = code.find(sa_marker)
if pos2 < 0:
    print("ERROR: SA marker not found")
    sys.exit(1)

insert_call = """    // Card-batch SA: move all flows from same card/port together
    if(!g_time_tight){
        memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
        memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
        memcpy(bk_port, fl_port, fl_count*sizeof(short));
        EvalMetrics cb_base=collect_metrics(m);
        run_sa_card_batch(m);
        EvalMetrics cb_after=collect_metrics(m);
        if(cb_after.fg>cb_base.fg||(cb_after.fg==cb_base.fg&&cb_after.jm>cb_base.jm)){
            memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
            memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
            memcpy(fl_port, bk_port, fl_count*sizeof(short));
        } else {
            run_neutral_swap(m);
            run_relaxed_swap(m);
            run_cross_dest_swap(m);
        }
    }

    """

code = code[:pos2] + insert_call + code[pos2:]

with open(src, 'w') as f:
    f.write(code)

print("v453 patch applied successfully")
