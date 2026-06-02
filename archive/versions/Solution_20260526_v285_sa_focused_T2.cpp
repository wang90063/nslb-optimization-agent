#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#if defined(_WIN32) || defined(_WIN64)
#define FAST_GET_CHAR getchar
#else
#define FAST_GET_CHAR getchar_unlocked
#endif
#define OUT_BUF_SIZE 1048576
static char out_buf[OUT_BUF_SIZE];
static int out_pos = 0;
inline void flush_out(){if(out_pos>0){fwrite(out_buf,1,out_pos,stdout);out_pos=0;}}
inline void write_char(char c){if(out_pos==OUT_BUF_SIZE)flush_out();out_buf[out_pos++]=c;}
inline void fast_write(int x){if(x<0){write_char('-');x=-x;}if(x==0){write_char('0');return;}char t[12];int l=0;while(x){t[l++]=(x%10)+'0';x/=10;}while(l--)write_char(t[l]);}
inline int fast_read_int(){int c=FAST_GET_CHAR();while(c<'0'||c>'9')c=FAST_GET_CHAR();int x=0;while(c>='0'&&c<='9'){x=x*10+(c-'0');c=FAST_GET_CHAR();}return x;}
#define MAX_CARDS 12800
#define MAX_FLOWS 400000
#define MAX_LEAFS 100
#define MAX_PORTS 32
#define MAX_PHASES 31
#define BITSET_SIZE ((MAX_CARDS*MAX_CARDS)/8+1)
static unsigned char seen_bits[BITSET_SIZE];
#define HT_SIZE (1<<20)
#define HT_MASK (HT_SIZE-1)
static int ht_key[HT_SIZE];
static int ht_val[HT_SIZE];
static int ht_used[MAX_FLOWS];
static int ht_used_cnt;
inline void ht_clear(){for(int i=0;i<ht_used_cnt;++i)ht_key[ht_used[i]]=-1;ht_used_cnt=0;}
inline int ht_find(int k){unsigned h=(unsigned)k;h=((h>>16)^h)*0x45d9f3b;h=((h>>16)^h)*0x45d9f3b;h=(h>>16)^h;int p=h&HT_MASK;while(1){if(ht_key[p]==k)return ht_val[p];if(ht_key[p]==-1)return -1;p=(p+1)&HT_MASK;}}
inline void ht_insert(int k,int v){unsigned h=(unsigned)k;h=((h>>16)^h)*0x45d9f3b;h=((h>>16)^h)*0x45d9f3b;h=(h>>16)^h;int p=h&HT_MASK;while(ht_key[p]!=-1)p=(p+1)&HT_MASK;ht_key[p]=k;ht_val[p]=v;ht_used[ht_used_cnt++]=p;}
static int fl_src[MAX_FLOWS],fl_dst[MAX_FLOWS];
static unsigned int fl_pmask[MAX_FLOWS];
static short fl_port[MAX_FLOWS];
static int fl_count;
static short out_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short in_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static int global_out[MAX_LEAFS][MAX_PORTS];
static int global_in[MAX_LEAFS][MAX_PORTS];
static int g_l,g_p,g_r,g_pr;
static int g_n,g_job_idx;
static clock_t g_start_clock;
static int g_time_tight;
static inline double elapsed_sec(){return (double)(clock()-g_start_clock)/CLOCKS_PER_SEC;}
static int g_hist_max_jm; // 历史最大 jm，用于判断当前 job 是否是 Maxsingler 瓶颈
static int fl_sl[MAX_FLOWS],fl_dl[MAX_FLOWS];
static int fl_order[MAX_FLOWS]; // for shuffled greedy
// Backup for strategy comparison
static short sv_out[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short sv_in[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short sv_port[MAX_FLOWS];
// Backup for swap safety
static short bk_out[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short bk_in[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short bk_port[MAX_FLOWS];
struct EvalMetrics{
    int score_jm;
    int score_fg;
    int jm;
    int fg;
    int ci;
    int future_over;
    long long future_sq;
};
inline int get_job_max(int m){
    int mx=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk)
            for(int ph=0;ph<m;++ph){
                int o=out_load[leaf][pk][ph];if(o>mx)mx=o;
                int iv=in_load[leaf][pk][ph];if(iv>mx)mx=iv;
            }
    return mx;
}

inline int get_future_gmax(int m){
    int gmax=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int mo=0,mi=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
            }
            int fo=global_out[leaf][pk]+mo;
            int fi=global_in[leaf][pk]+mi;
            int fv=fo>fi?fo:fi;
            if(fv>gmax)gmax=fv;
        }
    return gmax;
}

inline int get_cinphsc(int m){
    int cnt=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk)
            for(int ph=0;ph<m;++ph){
                int o=out_load[leaf][pk][ph];if(o>g_r)cnt+=(o-g_r);
                int iv=in_load[leaf][pk][ph];if(iv>g_r)cnt+=(iv-g_r);
            }
    return cnt;
}

inline EvalMetrics collect_metrics(int m){
    EvalMetrics em;
    em.jm=0;
    em.fg=0;
    em.ci=0;
    em.future_over=0;
    em.future_sq=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int mo=0,mi=0;
            for(int ph=0;ph<m;++ph){
                int o=out_load[leaf][pk][ph];
                if(o>em.jm)em.jm=o;
                if(o>g_r)em.ci+=(o-g_r);
                if(o>mo)mo=o;
                int iv=in_load[leaf][pk][ph];
                if(iv>em.jm)em.jm=iv;
                if(iv>g_r)em.ci+=(iv-g_r);
                if(iv>mi)mi=iv;
            }
            int fo=global_out[leaf][pk]+mo;
            int fi=global_in[leaf][pk]+mi;
            if(fo>em.fg)em.fg=fo;
            if(fi>em.fg)em.fg=fi;
            if(fo>g_r)em.future_over+=(fo-g_r);
            if(fi>g_r)em.future_over+=(fi-g_r);
            em.future_sq+=(long long)fo*fo+(long long)fi*fi;
        }
    em.score_jm=em.jm>g_r?em.jm:g_r;
    if(g_hist_max_jm>em.score_jm) em.score_jm=g_hist_max_jm;
    em.score_fg=em.fg>g_r?em.fg:g_r;
    return em;
}

inline int better_metrics(const EvalMetrics &a,const EvalMetrics &b){
    if(a.score_jm!=b.score_jm) return a.score_jm<b.score_jm;
    if(a.score_fg!=b.score_fg) return a.score_fg<b.score_fg;
    if(a.ci!=b.ci) return a.ci<b.ci;
    if(a.future_over!=b.future_over) return a.future_over<b.future_over;
    if(a.future_sq!=b.future_sq) return a.future_sq<b.future_sq;
    if(a.jm!=b.jm) return a.jm<b.jm;
    if(a.fg!=b.fg) return a.fg<b.fg;
    return 0;
}

void run_greedy_fgmax(int m, int hardcap, int rev=0){
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
        for(int pk=0;pk<g_p;++pk){
            int local_max=0,exceeds=0;
            int mo=0,mi=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                int v=o>iv?o:iv;if(v>local_max)local_max=v;
                if(o>mo)mo=o;
                if(iv>mi)mi=iv;
                if(hardcap&&(o>g_r||iv>g_r)) exceeds=1;
                m2&=m2-1;
            }
            for(int ph=0;ph<m;++ph){
                int o=out_load[sl][pk][ph];if(o>mo)mo=o;
                int iv=in_load[dl][pk][ph];if(iv>mi)mi=iv;
            }
            int fo=global_out[sl][pk]+mo;
            int fi=global_in[dl][pk]+mi;
            int fgv=fo>fi?fo:fi;
            int cost=local_max+fgv*3;
            if(exceeds) cost+=10000;
            if(cost<bc){bc=cost;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
}

// Strategy: run greedy with given parameters
// local_w: weight on local max, global_w: weight on global, hardcap: penalize >r
// rev: 0=normal, 1=reversed, 2+=use fl_order with seed-based shuffle
void run_greedy(int m, int local_w, int global_w, int hardcap, int rev=0){
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
        int bt_over=0x7fffffff,bt_sum=0x7fffffff;
        long long bt_sq=0x7fffffffffffffffLL;
        for(int pk=0;pk<g_p;++pk){
            int local_max=0;
            int exceeds=0;
            int use_future_tie=(hardcap&&g_p>=16&&g_hist_max_jm>g_r);
            int mo=0,mi=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                int v=o>iv?o:iv;if(v>local_max)local_max=v;
                if(hardcap&&(o>g_r||iv>g_r)) exceeds=1;
                if(hardcap&&g_p>=16&&v>g_r) use_future_tie=1;
                if(use_future_tie){
                    if(o>mo)mo=o;
                    if(iv>mi)mi=iv;
                }
                m2&=m2-1;
            }
            int go=global_out[sl][pk],gi=global_in[dl][pk];
            int gv=go>gi?go:gi;
            int cost=local_max*local_w+gv*global_w;
            if(exceeds) cost+=10000;
            int cand_over=0,cand_sum=0;
            long long cand_sq=0;
            if(use_future_tie){
                for(int ph=0;ph<m;++ph){
                    int o=out_load[sl][pk][ph];if(o>mo)mo=o;
                    int iv=in_load[dl][pk][ph];if(iv>mi)mi=iv;
                }
                int fo=go+mo;
                int fi=gi+mi;
                if(fo>g_r) cand_over+=(fo-g_r);
                if(fi>g_r) cand_over+=(fi-g_r);
                cand_sq=(long long)fo*fo+(long long)fi*fi;
                cand_sum=fo+fi;
            }
            if(cost<bc){
                bc=cost;bp=pk;
                bt_over=cand_over;
                bt_sq=cand_sq;
                bt_sum=cand_sum;
            } else if(use_future_tie&&cost==bc){
                if(cand_over<bt_over ||
                   (cand_over==bt_over && (cand_sq<bt_sq ||
                   (cand_sq==bt_sq && cand_sum<bt_sum)))){
                    bp=pk;
                    bt_over=cand_over;
                    bt_sq=cand_sq;
                    bt_sum=cand_sum;
                }
            }
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
}

// FTRL-inspired greedy: quadratic penalty on global load
// sc_div controls penalty strength: smaller = stronger quadratic
void run_greedy_ftrl(int m, int hardcap, int rev=0, int sc_div=2, int local_w=2){
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
    int scale = g_r * g_n / sc_div;
    if(scale < 1) scale = 1;
    for(int ii=0;ii<fl_count;++ii){
        int i;
        if(rev==0) i=ii;
        else if(rev==1) i=fl_count-1-ii;
        else i=fl_order[ii];
        int sl=fl_sl[i],dl=fl_dl[i];
        if(sl==dl){fl_port[i]=-1;continue;}
        unsigned int mask=fl_pmask[i];
        int bp=0,bc=0x7fffffff;
        for(int pk=0;pk<g_p;++pk){
            int local_max=0,exceeds=0;
            int mo=0,mi=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                int v=o>iv?o:iv;if(v>local_max)local_max=v;
                if(o>mo)mo=o; if(iv>mi)mi=iv;
                if(hardcap&&(o>g_r||iv>g_r)) exceeds=1;
                m2&=m2-1;
            }
            for(int ph=0;ph<m;++ph){
                int o=out_load[sl][pk][ph];if(o>mo)mo=o;
                int iv=in_load[dl][pk][ph];if(iv>mi)mi=iv;
            }
            int fo=global_out[sl][pk]+mo;
            int fi=global_in[dl][pk]+mi;
            int gv=fo>fi?fo:fi;
            int cost=local_max*local_w + gv + gv*gv/scale;
            if(exceeds) cost+=10000;
            if(cost<bc){bc=cost;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
}

// Method A: Exponential Potential Function
// 对高负载端口的惩罚指数级增长，理论上对 min-max 目标最优
// eta controls sensitivity: higher = more aggressive avoidance of high-load ports
void run_greedy_exp(int m, int hardcap, int rev=0, int eta=3){
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
    int scale = g_r * g_n;
    if(scale < 2) scale = 2;
    for(int ii=0;ii<fl_count;++ii){
        int i;
        if(rev==0) i=ii;
        else if(rev==1) i=fl_count-1-ii;
        else i=fl_order[ii];
        int sl=fl_sl[i],dl=fl_dl[i];
        if(sl==dl){fl_port[i]=-1;continue;}
        unsigned int mask=fl_pmask[i];
        int bp=0,bc=0x7fffffff;
        for(int pk=0;pk<g_p;++pk){
            int local_max=0,exceeds=0;
            int mo=0,mi=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                int v=o>iv?o:iv;if(v>local_max)local_max=v;
                if(o>mo)mo=o; if(iv>mi)mi=iv;
                if(hardcap&&(o>g_r||iv>g_r)) exceeds=1;
                m2&=m2-1;
            }
            for(int ph=0;ph<m;++ph){
                int o=out_load[sl][pk][ph];if(o>mo)mo=o;
                int iv=in_load[dl][pk][ph];if(iv>mi)mi=iv;
            }
            int fo=global_out[sl][pk]+mo;
            int fi=global_in[dl][pk]+mi;
            int gv=fo>fi?fo:fi;
            // 指数近似: gv + gv^3/(scale^2) — 比二次更强的高负载惩罚
            int exp_pen = gv + (long long)gv*gv*gv/(long long)scale/scale*eta;
            int cost=local_max*2 + exp_pen;
            if(exceeds) cost+=10000;
            if(cost<bc){bc=cost;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
}

// Method B: Adaptive FTRL — 早期 job 更保守（强惩罚），晚期更激进
// 核心思想：早期 job 不知道未来，应该更均匀分布；晚期 job 全局状态已定，可以激进优化
void run_greedy_ftrl_adaptive(int m, int hardcap, int rev=0){
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
    // 早期 job: sc_div 小 → scale 小 → 惩罚强 → 更保守
    // 晚期 job: sc_div 大 → scale 大 → 惩罚弱 → 更激进
    int sc_div = 1 + (g_job_idx * 3) / g_n;  // 1→4 随 job 进度
    int scale = g_r * g_n / sc_div;
    if(scale < 1) scale = 1;
    for(int ii=0;ii<fl_count;++ii){
        int i;
        if(rev==0) i=ii;
        else if(rev==1) i=fl_count-1-ii;
        else i=fl_order[ii];
        int sl=fl_sl[i],dl=fl_dl[i];
        if(sl==dl){fl_port[i]=-1;continue;}
        unsigned int mask=fl_pmask[i];
        int bp=0,bc=0x7fffffff;
        for(int pk=0;pk<g_p;++pk){
            int local_max=0,exceeds=0;
            int mo=0,mi=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                int v=o>iv?o:iv;if(v>local_max)local_max=v;
                if(o>mo)mo=o; if(iv>mi)mi=iv;
                if(hardcap&&(o>g_r||iv>g_r)) exceeds=1;
                m2&=m2-1;
            }
            for(int ph=0;ph<m;++ph){
                int o=out_load[sl][pk][ph];if(o>mo)mo=o;
                int iv=in_load[dl][pk][ph];if(iv>mi)mi=iv;
            }
            int fo=global_out[sl][pk]+mo;
            int fi=global_in[dl][pk]+mi;
            int gv=fo>fi?fo:fi;
            int cost=local_max*2 + gv + gv*gv/scale;
            if(exceeds) cost+=10000;
            if(cost<bc){bc=cost;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
}

void run_swap(int m){
    int pre_max=get_job_max(m);
    if(pre_max<=g_r) return;
    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));
    for(int iter=0;iter<20;++iter){
        int mx=get_job_max(m);
        if(mx<=g_r) break;
        int improved=0;
        for(int i=0;i<fl_count&&!improved;++i){
            int sl=fl_sl[i],dl=fl_dl[i];
            if(sl==dl) continue;
            int cp=fl_port[i];
            unsigned int mask=fl_pmask[i];
            int on_bn=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                if(out_load[sl][cp][ph]==mx||in_load[dl][cp][ph]==mx){on_bn=1;break;}
                m2&=m2-1;
            }
            if(!on_bn) continue;
            int best_new=-1,best_new_max=mx;
            for(int pk=0;pk<g_p;++pk){
                if(pk==cp) continue;
                int nm=0;
                m2=mask;
                while(m2){
                    int ph=__builtin_ctz(m2);
                    int no=out_load[sl][pk][ph]+1;if(no>nm)nm=no;
                    int ni=in_load[dl][pk][ph]+1;if(ni>nm)nm=ni;
                    int oo=out_load[sl][cp][ph]-1;if(oo>nm)nm=oo;
                    int oi=in_load[dl][cp][ph]-1;if(oi>nm)nm=oi;
                    m2&=m2-1;
                }
                if(nm<best_new_max){best_new_max=nm;best_new=pk;}
            }
            if(best_new>=0){
                m2=mask;
                while(m2){int ph=__builtin_ctz(m2);out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;out_load[sl][best_new][ph]++;in_load[dl][best_new][ph]++;m2&=m2-1;}
                fl_port[i]=(short)best_new;
                improved=1;
            }
        }
        if(!improved) break;
    }
    int post_max=get_job_max(m);
    if(post_max>=pre_max){
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

void run_jm_repair(int m){
    int pre_max=get_job_max(m);
    if(pre_max<=g_r) return;
    if(pre_max>g_r+1) return;
    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));
    for(int iter=0;iter<300;++iter){
        int improved=0;
        for(int i=0;i<fl_count&&!improved;++i){
            int sl=fl_sl[i],dl=fl_dl[i];
            if(sl==dl) continue;
            int cp=fl_port[i];
            if(cp<0) continue;
            unsigned int mask=fl_pmask[i];
            int on_overload=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                if(out_load[sl][cp][ph]>g_r||in_load[dl][cp][ph]>g_r)
                    {on_overload=1;break;}
                m2&=m2-1;
            }
            if(!on_overload) continue;
            // Level 1: simple move
            int best_pk=-1,best_nm=0x7fffffff;
            for(int pk=0;pk<g_p;++pk){
                if(pk==cp) continue;
                int ok=1,nm=0;
                m2=mask;
                while(m2){
                    int ph=__builtin_ctz(m2);
                    int no=out_load[sl][pk][ph]+1;
                    int ni=in_load[dl][pk][ph]+1;
                    if(no>g_r||ni>g_r){ok=0;break;}
                    if(no>nm)nm=no; if(ni>nm)nm=ni;
                    m2&=m2-1;
                }
                if(ok&&nm<best_nm){best_nm=nm;best_pk=pk;}
            }
            if(best_pk>=0){
                m2=mask;
                while(m2){int ph=__builtin_ctz(m2);
                    out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;
                    out_load[sl][best_pk][ph]++;in_load[dl][best_pk][ph]++;
                    m2&=m2-1;}
                fl_port[i]=(short)best_pk;
                improved=1;
                continue;
            }
            // Level 2: chain move — find a blocking flow to move first
            for(int pk=0;pk<g_p&&!improved;++pk){
                if(pk==cp) continue;
                int src_ok=1,dst_ok=1;
                m2=mask;
                while(m2){
                    int ph=__builtin_ctz(m2);
                    if(out_load[sl][pk][ph]+1>g_r) src_ok=0;
                    if(in_load[dl][pk][ph]+1>g_r) dst_ok=0;
                    m2&=m2-1;
                }
                if(!src_ok&&!dst_ok) continue;
                // Case A: source ok, dest blocks
                if(src_ok&&!dst_ok){
                    int block_ph=-1;
                    m2=mask;
                    while(m2){
                        int ph=__builtin_ctz(m2);
                        if(in_load[dl][pk][ph]+1>g_r){block_ph=ph;break;}
                        m2&=m2-1;
                    }
                    if(block_ph<0) continue;
                    for(int j=0;j<fl_count&&!improved;++j){
                        if(j==i) continue;
                        if(fl_dl[j]!=dl||fl_port[j]!=pk) continue;
                        if(fl_sl[j]==fl_dl[j]) continue;
                        if(!(fl_pmask[j]&(1u<<block_ph))) continue;
                        unsigned int gmask=fl_pmask[j];
                        int gsl=fl_sl[j],gdl=fl_dl[j];
                        for(int pz=0;pz<g_p;++pz){
                            if(pz==pk) continue;
                            int gok=1;
                            unsigned int gm=gmask;
                            while(gm){
                                int gph=__builtin_ctz(gm);
                                if(out_load[gsl][pz][gph]+1>g_r||
                                   in_load[gdl][pz][gph]+1>g_r){gok=0;break;}
                                gm&=gm-1;
                            }
                            if(!gok) continue;
                            int fok=1;
                            unsigned int fm=mask;
                            while(fm){
                                int fph=__builtin_ctz(fm);
                                int adj=(gmask&(1u<<fph))?-1:0;
                                if(in_load[dl][pk][fph]+adj+1>g_r){fok=0;break;}
                                fm&=fm-1;
                            }
                            if(!fok) continue;
                            gm=gmask;
                            while(gm){int gph=__builtin_ctz(gm);
                                out_load[gsl][pk][gph]--;in_load[gdl][pk][gph]--;
                                out_load[gsl][pz][gph]++;in_load[gdl][pz][gph]++;
                                gm&=gm-1;}
                            fl_port[j]=(short)pz;
                            fm=mask;
                            while(fm){int fph=__builtin_ctz(fm);
                                out_load[sl][cp][fph]--;in_load[dl][cp][fph]--;
                                out_load[sl][pk][fph]++;in_load[dl][pk][fph]++;
                                fm&=fm-1;}
                            fl_port[i]=(short)pk;
                            improved=1; break;
                        }
                    }
                }
                // Case B: dest ok, source blocks
                if(!improved&&dst_ok&&!src_ok){
                    int block_ph=-1;
                    m2=mask;
                    while(m2){
                        int ph=__builtin_ctz(m2);
                        if(out_load[sl][pk][ph]+1>g_r){block_ph=ph;break;}
                        m2&=m2-1;
                    }
                    if(block_ph<0) continue;
                    for(int j=0;j<fl_count&&!improved;++j){
                        if(j==i) continue;
                        if(fl_sl[j]!=sl||fl_port[j]!=pk) continue;
                        if(fl_sl[j]==fl_dl[j]) continue;
                        if(!(fl_pmask[j]&(1u<<block_ph))) continue;
                        unsigned int gmask=fl_pmask[j];
                        int gsl=fl_sl[j],gdl=fl_dl[j];
                        for(int pz=0;pz<g_p;++pz){
                            if(pz==pk) continue;
                            int gok=1;
                            unsigned int gm=gmask;
                            while(gm){
                                int gph=__builtin_ctz(gm);
                                if(out_load[gsl][pz][gph]+1>g_r||
                                   in_load[gdl][pz][gph]+1>g_r){gok=0;break;}
                                gm&=gm-1;
                            }
                            if(!gok) continue;
                            int fok=1;
                            unsigned int fm=mask;
                            while(fm){
                                int fph=__builtin_ctz(fm);
                                int adj=(gmask&(1u<<fph))?-1:0;
                                if(out_load[sl][pk][fph]+adj+1>g_r){fok=0;break;}
                                fm&=fm-1;
                            }
                            if(!fok) continue;
                            gm=gmask;
                            while(gm){int gph=__builtin_ctz(gm);
                                out_load[gsl][pk][gph]--;in_load[gdl][pk][gph]--;
                                out_load[gsl][pz][gph]++;in_load[gdl][pz][gph]++;
                                gm&=gm-1;}
                            fl_port[j]=(short)pz;
                            fm=mask;
                            while(fm){int fph=__builtin_ctz(fm);
                                out_load[sl][cp][fph]--;in_load[dl][cp][fph]--;
                                out_load[sl][pk][fph]++;in_load[dl][pk][fph]++;
                                fm&=fm-1;}
                            fl_port[i]=(short)pk;
                            improved=1; break;
                        }
                    }
                }
            }
        }
        if(!improved) break;
    }
    if(get_job_max(m)>=pre_max){
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

void run_global_swap(int m){
    int pre_gmax=get_future_gmax(m);
    int pre_jmax=get_job_max(m);
    if(pre_gmax<=g_r) return;
    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));
    for(int iter=0;iter<30;++iter){
        int cur_gmax=get_future_gmax(m);
        if(cur_gmax<=g_r) break;
        int bn_leaf=-1,bn_pk=-1,bn_dir=0;
        for(int leaf=0;leaf<g_l;++leaf)
            for(int pk=0;pk<g_p;++pk){
                int mo=0,mi=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                    if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
                }
                int fo=global_out[leaf][pk]+mo;
                int fi=global_in[leaf][pk]+mi;
                if(fo==cur_gmax){bn_leaf=leaf;bn_pk=pk;bn_dir=0;break;}
                if(fi==cur_gmax){bn_leaf=leaf;bn_pk=pk;bn_dir=1;break;}
            }
        if(bn_leaf<0) break;
        int improved=0;
        for(int i=0;i<fl_count&&!improved;++i){
            int sl=fl_sl[i],dl=fl_dl[i];
            if(sl==dl) continue;
            int cp=fl_port[i];
            int on_bn=0;
            if(bn_dir==0&&sl==bn_leaf&&cp==bn_pk) on_bn=1;
            if(bn_dir==1&&dl==bn_leaf&&cp==bn_pk) on_bn=1;
            if(!on_bn) continue;
            unsigned int mask=fl_pmask[i];
            int best_new=-1,best_new_gmax=cur_gmax;
            for(int pk=0;pk<g_p;++pk){
                if(pk==cp) continue;
                unsigned int m2=mask;
                int ok=1;
                while(m2){
                    int ph=__builtin_ctz(m2);
                    int no=out_load[sl][pk][ph]+1;
                    int ni=in_load[dl][pk][ph]+1;
                    if(no>pre_jmax||ni>pre_jmax){ok=0;break;}
                    m2&=m2-1;
                }
                if(!ok) continue;
                m2=mask;
                while(m2){int ph=__builtin_ctz(m2);out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;out_load[sl][pk][ph]++;in_load[dl][pk][ph]++;m2&=m2-1;}
                fl_port[i]=(short)pk;
                int ng=get_future_gmax(m);
                if(ng<best_new_gmax){best_new_gmax=ng;best_new=pk;}
                m2=mask;
                while(m2){int ph=__builtin_ctz(m2);out_load[sl][pk][ph]--;in_load[dl][pk][ph]--;out_load[sl][cp][ph]++;in_load[dl][cp][ph]++;m2&=m2-1;}
                fl_port[i]=(short)cp;
            }
            if(best_new>=0){
                unsigned int m2=mask;
                while(m2){int ph=__builtin_ctz(m2);out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;out_load[sl][best_new][ph]++;in_load[dl][best_new][ph]++;m2&=m2-1;}
                fl_port[i]=(short)best_new;
                improved=1;
            }
        }
        if(!improved) break;
    }
    if(get_future_gmax(m)>=pre_gmax||get_job_max(m)>pre_jmax){
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

static int lns_idx[MAX_FLOWS];
void run_lns(int m){
    int pre_gmax=get_future_gmax(m);
    int pre_jmax=get_job_max(m);
    if(pre_gmax<=g_r) return;
    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));
    for(int round=0;round<5;++round){
        int cur_gmax=get_future_gmax(m);
        if(cur_gmax<=g_r) break;
        int bn_leaf=-1,bn_pk=-1,bn_dir=0;
        for(int leaf=0;leaf<g_l&&bn_leaf<0;++leaf)
            for(int pk=0;pk<g_p;++pk){
                int mo=0,mi=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                    if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
                }
                int fo=global_out[leaf][pk]+mo;
                int fi=global_in[leaf][pk]+mi;
                if(fo==cur_gmax){bn_leaf=leaf;bn_pk=pk;bn_dir=0;break;}
                if(fi==cur_gmax){bn_leaf=leaf;bn_pk=pk;bn_dir=1;break;}
            }
        if(bn_leaf<0) break;
        int cnt=0;
        for(int i=0;i<fl_count;++i){
            if(fl_port[i]!=bn_pk) continue;
            if(bn_dir==0&&fl_sl[i]!=bn_leaf) continue;
            if(bn_dir==1&&fl_dl[i]!=bn_leaf) continue;
            lns_idx[cnt++]=i;
        }
        if(cnt==0) break;
        for(int k=0;k<cnt;++k){
            int i=lns_idx[k];
            int sl=fl_sl[i],dl=fl_dl[i];
            unsigned int m2=fl_pmask[i];
            while(m2){int ph=__builtin_ctz(m2);out_load[sl][bn_pk][ph]--;in_load[dl][bn_pk][ph]--;m2&=m2-1;}
        }
        for(int k=0;k<cnt;++k){
            int i=lns_idx[k];
            int sl=fl_sl[i],dl=fl_dl[i];
            unsigned int mask=fl_pmask[i];
            int bp=0,bc=0x7fffffff;
            for(int pk=0;pk<g_p;++pk){
                int local_max=0,exceeds=0;
                int mo=0,mi=0;
                unsigned int m2=mask;
                while(m2){
                    int ph=__builtin_ctz(m2);
                    int o=out_load[sl][pk][ph]+1;
                    int iv=in_load[dl][pk][ph]+1;
                    int v=o>iv?o:iv;if(v>local_max)local_max=v;
                    if(o>mo)mo=o;if(iv>mi)mi=iv;
                    if(o>pre_jmax||iv>pre_jmax) exceeds=1;
                    m2&=m2-1;
                }
                for(int ph=0;ph<m;++ph){
                    int o=out_load[sl][pk][ph];if(o>mo)mo=o;
                    int iv=in_load[dl][pk][ph];if(iv>mi)mi=iv;
                }
                int fo=global_out[sl][pk]+mo;
                int fi=global_in[dl][pk]+mi;
                int fgv=fo>fi?fo:fi;
                int cost=local_max+fgv*5;
                if(exceeds) cost+=10000;
                if(cost<bc){bc=cost;bp=pk;}
            }
            fl_port[i]=(short)bp;
            unsigned int m2=mask;
            while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
        }
    }
    if(get_future_gmax(m)>=pre_gmax||get_job_max(m)>pre_jmax){
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

// Reduce Cbtphsc: consolidate flows from same source card onto same port
// Constraint: never increase max_phase_load on any (leaf,port) — protects Maxmultir
// Improvement over original: try all ports as targets, iterate until convergence
static int pc_flows[MAX_FLOWS];
static int pc_mark[MAX_FLOWS];

inline int calc_phase_mask_cbt(const unsigned int *phase_masks, int m){
    int cnt=0;
    for(int ph=0;ph<m-1;++ph)
        if(phase_masks[ph]&&phase_masks[ph+1]&&phase_masks[ph]!=phase_masks[ph+1])
            cnt++;
    return cnt;
}

void run_port_consistency(int m){
    int max_iter=(g_time_tight)?2:5;
    for(int iter=0;iter<max_iter;++iter){
        int moved=0;
        for(int i=0;i<fl_count;++i) pc_mark[i]=0;
        for(int i=0;i<fl_count;++i){
            if(pc_mark[i]) continue;
            int src=fl_src[i];
            int cnt=0;
            for(int j=i;j<fl_count;++j){
                if(fl_src[j]==src && fl_sl[j]!=fl_dl[j] && fl_port[j]>=0){
                    pc_flows[cnt++]=j;
                    pc_mark[j]=1;
                }
            }
            if(cnt<=1) continue;
            int port_count[MAX_PORTS]={};
            for(int k=0;k<cnt;++k) port_count[fl_port[pc_flows[k]]]++;
            int best_tp=-1,best_total=0;
            unsigned int src_masks[MAX_PHASES]={};
            short src_ppc[MAX_PHASES][MAX_PORTS]={};
            for(int k=0;k<cnt;++k){
                int fi=pc_flows[k];
                int cp=fl_port[fi];
                unsigned int mask=fl_pmask[fi];
                while(mask){
                    int ph=__builtin_ctz(mask);
                    src_ppc[ph][cp]++;
                    src_masks[ph]|=(1u<<cp);
                    mask&=mask-1;
                }
            }
            int base_cbt=calc_phase_mask_cbt(src_masks,m);
            if(base_cbt>0&&cnt<=160){
                int best_cbt=base_cbt;
                long long best_pressure=0x7fffffffffffffffLL;
                for(int tp=0;tp<g_p;++tp){
                    if(port_count[tp]==cnt) continue;
                    unsigned int tmp_masks[MAX_PHASES];
                    short tmp_ppc[MAX_PHASES][MAX_PORTS];
                    memcpy(tmp_masks,src_masks,m*sizeof(unsigned int));
                    memcpy(tmp_ppc,src_ppc,m*sizeof(src_ppc[0]));
                    int can_move=0;
                    long long pressure=0;
                    for(int k=0;k<cnt;++k){
                        int fi=pc_flows[k];
                        int cp=fl_port[fi];
                        if(cp==tp){can_move++;continue;}
                        int sl=fl_sl[fi],dl=fl_dl[fi];
                        unsigned int mask=fl_pmask[fi];
                        int cur_max_out=0,cur_max_in=0;
                        for(int ph=0;ph<m;++ph){
                            if(out_load[sl][tp][ph]>cur_max_out)cur_max_out=out_load[sl][tp][ph];
                            if(in_load[dl][tp][ph]>cur_max_in)cur_max_in=in_load[dl][tp][ph];
                        }
                        unsigned int m2=mask; int ok=1;
                        while(m2){
                            int ph=__builtin_ctz(m2);
                            if(out_load[sl][tp][ph]+1>cur_max_out||
                               in_load[dl][tp][ph]+1>cur_max_in){ok=0;break;}
                            if(out_load[sl][tp][ph]>=g_r&&out_load[sl][cp][ph]<=g_r){ok=0;break;}
                            if(in_load[dl][tp][ph]>=g_r&&in_load[dl][cp][ph]<=g_r){ok=0;break;}
                            m2&=m2-1;
                        }
                        if(!ok) continue;
                        int useful=0;
                        m2=mask;
                        while(m2){
                            int ph=__builtin_ctz(m2);
                            if(tmp_ppc[ph][cp]==1 || !(tmp_masks[ph]&(1u<<tp))){
                                useful=1;
                                break;
                            }
                            m2&=m2-1;
                        }
                        if(!useful) continue;
                        can_move++;
                        pressure+=(long long)global_out[sl][tp]-global_out[sl][cp];
                        pressure+=(long long)global_in[dl][tp]-global_in[dl][cp];
                        m2=mask;
                        while(m2){
                            int ph=__builtin_ctz(m2);
                            tmp_ppc[ph][cp]--;
                            if(!tmp_ppc[ph][cp]) tmp_masks[ph]&=~(1u<<cp);
                            tmp_ppc[ph][tp]++;
                            tmp_masks[ph]|=(1u<<tp);
                            m2&=m2-1;
                        }
                    }
                    int after_cbt=calc_phase_mask_cbt(tmp_masks,m);
                    if(after_cbt<best_cbt||
                       (after_cbt==best_cbt&&
                        (pressure<best_pressure||
                         (pressure==best_pressure&&can_move>best_total)))){
                        best_cbt=after_cbt;
                        best_pressure=pressure;
                        best_total=can_move;
                        best_tp=tp;
                    }
                }
            } else {
                for(int tp=0;tp<g_p;++tp){
                    if(port_count[tp]==cnt) {best_tp=-1;break;}
                    int can_move=0;
                    for(int k=0;k<cnt;++k){
                        int fi=pc_flows[k];
                        if(fl_port[fi]==tp) {can_move++;continue;}
                        int sl=fl_sl[fi],dl=fl_dl[fi],cp=fl_port[fi];
                        unsigned int mask=fl_pmask[fi];
                        int cur_max_out=0,cur_max_in=0;
                        for(int ph=0;ph<m;++ph){
                            if(out_load[sl][tp][ph]>cur_max_out)cur_max_out=out_load[sl][tp][ph];
                            if(in_load[dl][tp][ph]>cur_max_in)cur_max_in=in_load[dl][tp][ph];
                        }
                        unsigned int m2=mask; int ok=1;
                        while(m2){
                            int ph=__builtin_ctz(m2);
                            if(out_load[sl][tp][ph]+1>cur_max_out||
                               in_load[dl][tp][ph]+1>cur_max_in){ok=0;break;}
                            if(out_load[sl][tp][ph]>=g_r&&out_load[sl][cp][ph]<=g_r){ok=0;break;}
                            if(in_load[dl][tp][ph]>=g_r&&in_load[dl][cp][ph]<=g_r){ok=0;break;}
                            m2&=m2-1;
                        }
                        if(ok) can_move++;
                    }
                    if(can_move>best_total){best_total=can_move;best_tp=tp;}
                }
            }
            if(best_tp<0) continue;
            int group_moved;
            do{
                group_moved=0;
                for(int k=0;k<cnt;++k){
                    int fi=pc_flows[k];
                    int cp=fl_port[fi];
                    if(cp==best_tp) continue;
                    int sl=fl_sl[fi],dl=fl_dl[fi];
                    unsigned int mask=fl_pmask[fi];
                    int useful=0;
                    unsigned int m2=mask;
                    while(m2){
                        int ph=__builtin_ctz(m2);
                        if(src_ppc[ph][cp]==1 || !(src_masks[ph]&(1u<<best_tp))){
                            useful=1;
                            break;
                        }
                        m2&=m2-1;
                    }
                    if(!useful) continue;
                    int cur_max_out=0,cur_max_in=0;
                    for(int ph=0;ph<m;++ph){
                        if(out_load[sl][best_tp][ph]>cur_max_out)cur_max_out=out_load[sl][best_tp][ph];
                        if(in_load[dl][best_tp][ph]>cur_max_in)cur_max_in=in_load[dl][best_tp][ph];
                    }
                    m2=mask; int ok=1;
                    while(m2){
                        int ph=__builtin_ctz(m2);
                        if(out_load[sl][best_tp][ph]+1>cur_max_out||
                           in_load[dl][best_tp][ph]+1>cur_max_in){ok=0;break;}
                        if(out_load[sl][best_tp][ph]>=g_r&&out_load[sl][cp][ph]<=g_r){ok=0;break;}
                        if(in_load[dl][best_tp][ph]>=g_r&&in_load[dl][cp][ph]<=g_r){ok=0;break;}
                        m2&=m2-1;
                    }
                    if(!ok) continue;
                    m2=mask;
                    while(m2){
                        int ph=__builtin_ctz(m2);
                        out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;
                        out_load[sl][best_tp][ph]++;in_load[dl][best_tp][ph]++;
                        src_ppc[ph][cp]--;
                        if(!src_ppc[ph][cp]) src_masks[ph]&=~(1u<<cp);
                        src_ppc[ph][best_tp]++;
                        src_masks[ph]|=(1u<<best_tp);
                        m2&=m2-1;
                    }
                    fl_port[fi]=(short)best_tp;
                    moved++;
                    group_moved=1;
                }
            }while(group_moved);
        }
        if(!moved) break;
    }
}

void run_port_consistency_perport_refine(int m){
    long long total_work=(long long)fl_count*(long long)m;
    if(total_work>100000) return;
    if(total_work>80000){
        if(!(g_p>=16&&m>=17&&fl_count<=5500)) return;
    }
    if(total_work>50000&&fl_count>5000) return;

    for(int iter=0;iter<2;++iter){
        int moved=0;
        for(int i=0;i<fl_count;++i) pc_mark[i]=0;
        for(int i=0;i<fl_count;++i){
            if(pc_mark[i]) continue;
            int src=fl_src[i];
            int cnt=0;
            for(int j=i;j<fl_count;++j){
                if(fl_src[j]==src && fl_sl[j]!=fl_dl[j] && fl_port[j]>=0){
                    pc_flows[cnt++]=j;
                    pc_mark[j]=1;
                }
            }
            if(cnt<=1||cnt>160) continue;

            unsigned int src_masks[MAX_PHASES]={};
            short src_ppc[MAX_PHASES][MAX_PORTS]={};
            for(int k=0;k<cnt;++k){
                int fi=pc_flows[k];
                int cp=fl_port[fi];
                unsigned int mask=fl_pmask[fi];
                while(mask){
                    int ph=__builtin_ctz(mask);
                    src_ppc[ph][cp]++;
                    src_masks[ph]|=(1u<<cp);
                    mask&=mask-1;
                }
            }

            for(int refine_round=0;refine_round<2;++refine_round){
                int base_cbt=calc_phase_mask_cbt(src_masks,m);
                if(base_cbt<=0) break;
                int max_used_cnt=6;
                if(total_work>50000&&g_p>=16&&m>=17&&fl_count<=5000) max_used_cnt=7;

                int used_ports[MAX_PORTS];
                int used_cnt=0;
                for(int pk=0;pk<g_p;++pk){
                    int seen=0;
                    for(int ph=0;ph<m;++ph){
                        if(src_ppc[ph][pk]){
                            seen=1;
                            break;
                        }
                    }
                    if(seen) used_ports[used_cnt++]=pk;
                }
                if(used_cnt<=1||used_cnt>max_used_cnt) break;

                int best_cp=-1,best_tp=-1,best_cbt=base_cbt,best_moves=0;
                long long best_pressure=0x7fffffffffffffffLL;
                for(int ui=0;ui<used_cnt;++ui){
                    int cp=used_ports[ui];
                    for(int vi=0;vi<used_cnt;++vi){
                        int tp=used_ports[vi];
                        if(tp==cp) continue;
                        unsigned int tmp_masks[MAX_PHASES];
                        short tmp_ppc[MAX_PHASES][MAX_PORTS];
                        memcpy(tmp_masks,src_masks,m*sizeof(unsigned int));
                        memcpy(tmp_ppc,src_ppc,m*sizeof(tmp_ppc[0]));
                        int can_move=0;
                        long long pressure=0;
                        for(int k=0;k<cnt;++k){
                            int fi=pc_flows[k];
                            if(fl_port[fi]!=cp) continue;
                            int sl=fl_sl[fi],dl=fl_dl[fi];
                            unsigned int mask=fl_pmask[fi];
                            int cur_max_out=0,cur_max_in=0;
                            for(int ph=0;ph<m;++ph){
                                if(out_load[sl][tp][ph]>cur_max_out)cur_max_out=out_load[sl][tp][ph];
                                if(in_load[dl][tp][ph]>cur_max_in)cur_max_in=in_load[dl][tp][ph];
                            }
                            unsigned int m2=mask; int ok=1;
                            while(m2){
                                int ph=__builtin_ctz(m2);
                                if(out_load[sl][tp][ph]+1>cur_max_out||
                                   in_load[dl][tp][ph]+1>cur_max_in){ok=0;break;}
                                if(out_load[sl][tp][ph]>=g_r&&out_load[sl][cp][ph]<=g_r){ok=0;break;}
                                if(in_load[dl][tp][ph]>=g_r&&in_load[dl][cp][ph]<=g_r){ok=0;break;}
                                m2&=m2-1;
                            }
                            if(!ok) continue;
                            int useful=0;
                            m2=mask;
                            while(m2){
                                int ph=__builtin_ctz(m2);
                                if(tmp_ppc[ph][cp]==1 || !(tmp_masks[ph]&(1u<<tp))){
                                    useful=1;
                                    break;
                                }
                                m2&=m2-1;
                            }
                            if(!useful) continue;
                            can_move++;
                            pressure+=(long long)global_out[sl][tp]-global_out[sl][cp];
                            pressure+=(long long)global_in[dl][tp]-global_in[dl][cp];
                            m2=mask;
                            while(m2){
                                int ph=__builtin_ctz(m2);
                                tmp_ppc[ph][cp]--;
                                if(!tmp_ppc[ph][cp]) tmp_masks[ph]&=~(1u<<cp);
                                tmp_ppc[ph][tp]++;
                                tmp_masks[ph]|=(1u<<tp);
                                m2&=m2-1;
                            }
                        }
                        if(!can_move) continue;
                        int after_cbt=calc_phase_mask_cbt(tmp_masks,m);
                        if(after_cbt<best_cbt||
                           (after_cbt==best_cbt&&after_cbt<base_cbt&&
                            (pressure<best_pressure||
                             (pressure==best_pressure&&can_move>best_moves)))){
                            best_cbt=after_cbt;
                            best_pressure=pressure;
                            best_moves=can_move;
                            best_cp=cp;
                            best_tp=tp;
                        }
                    }
                }
                if(best_cp<0||best_cbt>=base_cbt) break;

                int pass_moved;
                do{
                    pass_moved=0;
                    for(int k=0;k<cnt;++k){
                        int fi=pc_flows[k];
                        if(fl_port[fi]!=best_cp) continue;
                        int sl=fl_sl[fi],dl=fl_dl[fi];
                        unsigned int mask=fl_pmask[fi];
                        int useful=0;
                        unsigned int m2=mask;
                        while(m2){
                            int ph=__builtin_ctz(m2);
                            if(src_ppc[ph][best_cp]==1 || !(src_masks[ph]&(1u<<best_tp))){
                                useful=1;
                                break;
                            }
                            m2&=m2-1;
                        }
                        if(!useful) continue;
                        int cur_max_out=0,cur_max_in=0;
                        for(int ph=0;ph<m;++ph){
                            if(out_load[sl][best_tp][ph]>cur_max_out)cur_max_out=out_load[sl][best_tp][ph];
                            if(in_load[dl][best_tp][ph]>cur_max_in)cur_max_in=in_load[dl][best_tp][ph];
                        }
                        m2=mask; int ok=1;
                        while(m2){
                            int ph=__builtin_ctz(m2);
                            if(out_load[sl][best_tp][ph]+1>cur_max_out||
                               in_load[dl][best_tp][ph]+1>cur_max_in){ok=0;break;}
                            if(out_load[sl][best_tp][ph]>=g_r&&out_load[sl][best_cp][ph]<=g_r){ok=0;break;}
                            if(in_load[dl][best_tp][ph]>=g_r&&in_load[dl][best_cp][ph]<=g_r){ok=0;break;}
                            m2&=m2-1;
                        }
                        if(!ok) continue;
                        m2=mask;
                        while(m2){
                            int ph=__builtin_ctz(m2);
                            out_load[sl][best_cp][ph]--;in_load[dl][best_cp][ph]--;
                            out_load[sl][best_tp][ph]++;in_load[dl][best_tp][ph]++;
                            src_ppc[ph][best_cp]--;
                            if(!src_ppc[ph][best_cp]) src_masks[ph]&=~(1u<<best_cp);
                            src_ppc[ph][best_tp]++;
                            src_masks[ph]|=(1u<<best_tp);
                            m2&=m2-1;
                        }
                        fl_port[fi]=(short)best_tp;
                        moved++;
                        pass_moved=1;
                    }
                }while(pass_moved);
            }
        }
        if(!moved) break;
    }
}

// Neutral swap: reassign equivalent flows (same sl,dl,mask) to reduce Cbtphsc
// Uses direct Cbtphsc computation (adjacent-phase port set consistency)
static int ns_valid_cnt;

struct NSKey { int sl; int dl; unsigned int mask; int idx; };
static NSKey ns_keys[MAX_FLOWS];

int ns_cmp(const void*a,const void*b){
    const NSKey*x=(const NSKey*)a;const NSKey*y=(const NSKey*)b;
    if(x->sl!=y->sl)return x->sl-y->sl;
    if(x->dl!=y->dl)return x->dl-y->dl;
    if(x->mask!=y->mask)return (x->mask<y->mask)?-1:1;
    return 0;
}

// card_phase_portmask[card][phase] = bitmask of ports used by card in that phase
static unsigned int cpm[MAX_CARDS][MAX_PHASES];
// card_phase_port_cnt[card][phase][port] = number of flows from card on port in phase
static short cppc[MAX_CARDS][MAX_PHASES][MAX_PORTS];

inline int card_cbtphsc(int card, int m){
    int cnt=0;
    for(int ph=0;ph<m-1;++ph)
        if(cpm[card][ph]&&cpm[card][ph+1]&&cpm[card][ph]!=cpm[card][ph+1])
            cnt++;
    return cnt;
}

void run_neutral_swap(int m){
    // Build card_phase_portmask and card_phase_port_cnt
    memset(cpm,0,sizeof(cpm));
    memset(cppc,0,sizeof(cppc));
    ns_valid_cnt=0;
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
        int c=fl_src[i],p=fl_port[i];
        unsigned int mk=fl_pmask[i];
        while(mk){
            int ph=__builtin_ctz(mk);
            cppc[c][ph][p]++;
            cpm[c][ph]|=(1u<<p);
            mk&=mk-1;
        }
        ns_keys[ns_valid_cnt]={fl_sl[i],fl_dl[i],fl_pmask[i],i};
        ns_valid_cnt++;
    }
    qsort(ns_keys,ns_valid_cnt,sizeof(NSKey),ns_cmp);
    int ns_max_iter=3;
    for(int iter=0;iter<ns_max_iter;++iter){
        int improved=0;
        int g_start=0;
        while(g_start<ns_valid_cnt){
            int g_end=g_start+1;
            while(g_end<ns_valid_cnt&&ns_keys[g_end].sl==ns_keys[g_start].sl
                  &&ns_keys[g_end].dl==ns_keys[g_start].dl
                  &&ns_keys[g_end].mask==ns_keys[g_start].mask) g_end++;
            int gsz=g_end-g_start;
            if(gsz>=2&&gsz<=200){
                for(int a=g_start;a<g_end;++a){
                    int i=ns_keys[a].idx;
                    int pi=fl_port[i],ci=fl_src[i];
                    if(pi<0) continue;
                    for(int b=a+1;b<g_end;++b){
                        int j=ns_keys[b].idx;
                        int pj=fl_port[j],cj=fl_src[j];
                        if(pj<0||pi==pj||ci==cj) continue;
                        // Compute Cbtphsc before for both cards
                        int before=card_cbtphsc(ci,m)+card_cbtphsc(cj,m);
                        // Tentatively swap: ci from pi to pj, cj from pj to pi
                        unsigned int mk=fl_pmask[i];
                        while(mk){int ph=__builtin_ctz(mk);
                            cppc[ci][ph][pi]--;if(!cppc[ci][ph][pi])cpm[ci][ph]&=~(1u<<pi);
                            cppc[ci][ph][pj]++;cpm[ci][ph]|=(1u<<pj);
                            mk&=mk-1;}
                        mk=fl_pmask[j];
                        while(mk){int ph=__builtin_ctz(mk);
                            cppc[cj][ph][pj]--;if(!cppc[cj][ph][pj])cpm[cj][ph]&=~(1u<<pj);
                            cppc[cj][ph][pi]++;cpm[cj][ph]|=(1u<<pi);
                            mk&=mk-1;}
                        int after=card_cbtphsc(ci,m)+card_cbtphsc(cj,m);
                        if(after<before){
                            fl_port[i]=(short)pj;fl_port[j]=(short)pi;
                            pi=pj; improved++;
                        } else {
                            // Revert
                            mk=fl_pmask[i];
                            while(mk){int ph=__builtin_ctz(mk);
                                cppc[ci][ph][pj]--;if(!cppc[ci][ph][pj])cpm[ci][ph]&=~(1u<<pj);
                                cppc[ci][ph][pi]++;cpm[ci][ph]|=(1u<<pi);
                                mk&=mk-1;}
                            mk=fl_pmask[j];
                            while(mk){int ph=__builtin_ctz(mk);
                                cppc[cj][ph][pi]--;if(!cppc[cj][ph][pi])cpm[cj][ph]&=~(1u<<pi);
                                cppc[cj][ph][pj]++;cpm[cj][ph]|=(1u<<pj);
                                mk&=mk-1;}
                        }
                    }
                }
            }
            g_start=g_end;
        }
        if(!improved) break;
    }
}

// Relaxed swap: on normal-r jobs, widen groups to the whole source leaf; on
// r<=2 jobs, keep the original same-(sl,dl) grouping to avoid MM regressions.
struct RSKey { int sl; int dl; int idx; };
static RSKey rs_keys[MAX_FLOWS];
static int rs_valid_cnt;
static int rs_sort_by_dl;

int rs_cmp(const void*a,const void*b){
    const RSKey*x=(const RSKey*)a;const RSKey*y=(const RSKey*)b;
    if(x->sl!=y->sl)return x->sl-y->sl;
    if(rs_sort_by_dl&&x->dl!=y->dl)return x->dl-y->dl;
    return 0;
}

void run_relaxed_swap(int m){
    int sl_only_relaxed=(g_r>=3);
    int rs_gsz_cap=sl_only_relaxed?300:150;
    rs_sort_by_dl=!sl_only_relaxed;
    // Precompute max_phase_load per (leaf, port)
    static short max_out[MAX_LEAFS][MAX_PORTS];
    static short max_in[MAX_LEAFS][MAX_PORTS];
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            short mo=0,mi=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
            }
            max_out[leaf][pk]=mo; max_in[leaf][pk]=mi;
        }
    rs_valid_cnt=0;
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
        rs_keys[rs_valid_cnt]={fl_sl[i],fl_dl[i],i};
        rs_valid_cnt++;
    }
    qsort(rs_keys,rs_valid_cnt,sizeof(RSKey),rs_cmp);
    // Rebuild cpm/cppc for Cbtphsc evaluation
    memset(cpm,0,sizeof(cpm));memset(cppc,0,sizeof(cppc));
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
        int c=fl_src[i],p=fl_port[i];
        unsigned int mk=fl_pmask[i];
        while(mk){int ph=__builtin_ctz(mk);cppc[c][ph][p]++;cpm[c][ph]|=(1u<<p);mk&=mk-1;}
    }
    int rs_max_iter=5;
    for(int iter=0;iter<rs_max_iter;++iter){
        int improved=0;
        int g_start=0;
        while(g_start<rs_valid_cnt){
            int g_end=g_start+1;
            while(g_end<rs_valid_cnt&&rs_keys[g_end].sl==rs_keys[g_start].sl
                  &&(sl_only_relaxed||rs_keys[g_end].dl==rs_keys[g_start].dl)) g_end++;
            int gsz=g_end-g_start;
            if(gsz>=2&&gsz<=rs_gsz_cap){
                for(int a=g_start;a<g_end;++a){
                    int i=rs_keys[a].idx;
                    int pi=fl_port[i],ci=fl_src[i],sl=fl_sl[i],dl_i=fl_dl[i];
                    if(pi<0) continue;
                    unsigned int mi_mask=fl_pmask[i];
                    for(int b=a+1;b<g_end;++b){
                        int j=rs_keys[b].idx;
                        int pj=fl_port[j],cj=fl_src[j];
                        if(pj<0||pi==pj||ci==cj) continue;
                        if(fl_pmask[i]==fl_pmask[j]&&fl_dl[j]==dl_i) continue;
                        int dl_j=fl_dl[j];
                        unsigned int mj_mask=fl_pmask[j];
                        unsigned int only_i=mi_mask&~mj_mask;
                        unsigned int only_j=mj_mask&~mi_mask;
                        int ok=1;
                        unsigned int m2;
                        if(dl_i==dl_j){
                            m2=only_i;
                            while(m2){int ph=__builtin_ctz(m2);
                                if(out_load[sl][pj][ph]+1>max_out[sl][pj]||
                                   in_load[dl_i][pj][ph]+1>max_in[dl_i][pj]){ok=0;break;}
                                if(out_load[sl][pi][ph]-1<0||in_load[dl_i][pi][ph]-1<0){ok=0;break;}
                                m2&=m2-1;}
                            if(!ok) continue;
                            m2=only_j;
                            while(m2){int ph=__builtin_ctz(m2);
                                if(out_load[sl][pi][ph]+1>max_out[sl][pi]||
                                   in_load[dl_i][pi][ph]+1>max_in[dl_i][pi]){ok=0;break;}
                                if(out_load[sl][pj][ph]-1<0||in_load[dl_i][pj][ph]-1<0){ok=0;break;}
                                m2&=m2-1;}
                        } else {
                            m2=only_i;
                            while(m2){int ph=__builtin_ctz(m2);
                                if(out_load[sl][pj][ph]+1>max_out[sl][pj]){ok=0;break;}
                                if(out_load[sl][pi][ph]-1<0){ok=0;break;}
                                m2&=m2-1;}
                            if(!ok) continue;
                            m2=only_j;
                            while(m2){int ph=__builtin_ctz(m2);
                                if(out_load[sl][pi][ph]+1>max_out[sl][pi]){ok=0;break;}
                                if(out_load[sl][pj][ph]-1<0){ok=0;break;}
                                m2&=m2-1;}
                            if(!ok) continue;
                            m2=mi_mask;
                            while(m2){int ph=__builtin_ctz(m2);
                                if(in_load[dl_i][pj][ph]+1>max_in[dl_i][pj]){ok=0;break;}
                                if(in_load[dl_i][pi][ph]-1<0){ok=0;break;}
                                m2&=m2-1;}
                            if(!ok) continue;
                            m2=mj_mask;
                            while(m2){int ph=__builtin_ctz(m2);
                                if(in_load[dl_j][pi][ph]+1>max_in[dl_j][pi]){ok=0;break;}
                                if(in_load[dl_j][pj][ph]-1<0){ok=0;break;}
                                m2&=m2-1;}
                        }
                        if(!ok) continue;
                        // Check Cbtphsc improvement
                        int before=card_cbtphsc(ci,m)+card_cbtphsc(cj,m);
                        // Apply swap
                        unsigned int mk;
                        mk=mi_mask;while(mk){int ph=__builtin_ctz(mk);
                            cppc[ci][ph][pi]--;if(!cppc[ci][ph][pi])cpm[ci][ph]&=~(1u<<pi);
                            cppc[ci][ph][pj]++;cpm[ci][ph]|=(1u<<pj);mk&=mk-1;}
                        mk=mj_mask;while(mk){int ph=__builtin_ctz(mk);
                            cppc[cj][ph][pj]--;if(!cppc[cj][ph][pj])cpm[cj][ph]&=~(1u<<pj);
                            cppc[cj][ph][pi]++;cpm[cj][ph]|=(1u<<pi);mk&=mk-1;}
                        int after=card_cbtphsc(ci,m)+card_cbtphsc(cj,m);
                        if(after<before){
                            // Commit: update loads
                            if(dl_i==dl_j){
                                m2=only_i;while(m2){int ph=__builtin_ctz(m2);
                                    out_load[sl][pi][ph]--;in_load[dl_i][pi][ph]--;
                                    out_load[sl][pj][ph]++;in_load[dl_i][pj][ph]++;m2&=m2-1;}
                                m2=only_j;while(m2){int ph=__builtin_ctz(m2);
                                    out_load[sl][pj][ph]--;in_load[dl_i][pj][ph]--;
                                    out_load[sl][pi][ph]++;in_load[dl_i][pi][ph]++;m2&=m2-1;}
                            } else {
                                m2=only_i;while(m2){int ph=__builtin_ctz(m2);
                                    out_load[sl][pi][ph]--;out_load[sl][pj][ph]++;m2&=m2-1;}
                                m2=only_j;while(m2){int ph=__builtin_ctz(m2);
                                    out_load[sl][pj][ph]--;out_load[sl][pi][ph]++;m2&=m2-1;}
                                m2=mi_mask;while(m2){int ph=__builtin_ctz(m2);
                                    in_load[dl_i][pi][ph]--;in_load[dl_i][pj][ph]++;m2&=m2-1;}
                                m2=mj_mask;while(m2){int ph=__builtin_ctz(m2);
                                    in_load[dl_j][pj][ph]--;in_load[dl_j][pi][ph]++;m2&=m2-1;}
                            }
                            fl_port[i]=(short)pj;fl_port[j]=(short)pi;
                            pi=pj;improved++;
                        } else {
                            // Revert cpm/cppc
                            mk=mi_mask;while(mk){int ph=__builtin_ctz(mk);
                                cppc[ci][ph][pj]--;if(!cppc[ci][ph][pj])cpm[ci][ph]&=~(1u<<pj);
                                cppc[ci][ph][pi]++;cpm[ci][ph]|=(1u<<pi);mk&=mk-1;}
                            mk=mj_mask;while(mk){int ph=__builtin_ctz(mk);
                                cppc[cj][ph][pi]--;if(!cppc[cj][ph][pi])cpm[cj][ph]&=~(1u<<pi);
                                cppc[cj][ph][pj]++;cpm[cj][ph]|=(1u<<pj);mk&=mk-1;}
                        }
                    }
                }
            }
            g_start=g_end;
        }
        if(!improved) break;
    }
}

// Cross-dest swap for Cbtphsc on low-r cases (load-safe)
static int cd_idx[MAX_FLOWS];
static int cd_off[MAX_LEAFS*MAX_PORTS+1];
static int cd_bucket_cnt[MAX_LEAFS*MAX_PORTS];

void run_cross_dest_swap(int m){
    static short cd_max_out[MAX_LEAFS][MAX_PORTS];
    static short cd_max_in[MAX_LEAFS][MAX_PORTS];
    int cd_max_iter=(g_time_tight)?1:3;
    for(int iter=0;iter<cd_max_iter;++iter){
        for(int leaf=0;leaf<g_l;++leaf)
            for(int pk=0;pk<g_p;++pk){
                short mo=0,mi=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                    if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
                }
                cd_max_out[leaf][pk]=mo;cd_max_in[leaf][pk]=mi;
            }
        memset(cpm,0,sizeof(cpm));memset(cppc,0,sizeof(cppc));
        for(int i=0;i<fl_count;++i){
            if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
            int c=fl_src[i],p=fl_port[i];
            unsigned int mk=fl_pmask[i];
            while(mk){int ph=__builtin_ctz(mk);cppc[c][ph][p]++;cpm[c][ph]|=(1u<<p);mk&=mk-1;}
        }
        memset(cd_bucket_cnt,0,g_l*g_p*sizeof(int));
        for(int i=0;i<fl_count;++i){
            if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
            cd_bucket_cnt[fl_sl[i]*g_p+fl_port[i]]++;
        }
        cd_off[0]=0;
        for(int b=0;b<g_l*g_p;++b) cd_off[b+1]=cd_off[b]+cd_bucket_cnt[b];
        memset(cd_bucket_cnt,0,g_l*g_p*sizeof(int));
        for(int i=0;i<fl_count;++i){
            if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
            int b=fl_sl[i]*g_p+fl_port[i];
            cd_idx[cd_off[b]+cd_bucket_cnt[b]]=i;
            cd_bucket_cnt[b]++;
        }
        int improved=0;
        for(int fi=0;fi<fl_count;++fi){
            int sl=fl_sl[fi],dl_a=fl_dl[fi],px=fl_port[fi],ci=fl_src[fi];
            if(sl==dl_a||px<0) continue;
            if(card_cbtphsc(ci,m)==0) continue;
            int dp_cnt[32]={};
            for(int ph=0;ph<m;++ph)
                for(int pk=0;pk<g_p;++pk) dp_cnt[pk]+=cppc[ci][ph][pk];
            int dp=-1,dp_best=0;
            for(int pk=0;pk<g_p;++pk) if(dp_cnt[pk]>dp_best){dp_best=dp_cnt[pk];dp=pk;}
            if(dp<0||px==dp) continue;
            int py=dp;
            unsigned int mask_a=fl_pmask[fi];
            int bucket=sl*g_p+py;
            int bstart=cd_off[bucket],bend=cd_off[bucket+1];
            int best_wt=0,best_j=-1;
            for(int bi=bstart;bi<bend;++bi){
                int j=cd_idx[bi];
                if(j==fi) continue;
                int cj=fl_src[j];
                if(cj==ci) continue;
                if(fl_port[j]!=py) continue;
                int dl_b=fl_dl[j];
                unsigned int mask_b=fl_pmask[j];
                unsigned int only_a=mask_a&~mask_b,only_b=mask_b&~mask_a;
                int ok=1;unsigned int m2;
                m2=only_a;while(m2){int ph=__builtin_ctz(m2);
                    if(out_load[sl][py][ph]+1>cd_max_out[sl][py]){ok=0;break;}m2&=m2-1;}
                if(!ok) continue;
                m2=only_b;while(m2){int ph=__builtin_ctz(m2);
                    if(out_load[sl][px][ph]+1>cd_max_out[sl][px]){ok=0;break;}m2&=m2-1;}
                if(!ok) continue;
                if(dl_a==dl_b){
                    m2=only_a;while(m2){int ph=__builtin_ctz(m2);
                        if(in_load[dl_a][py][ph]+1>cd_max_in[dl_a][py]){ok=0;break;}m2&=m2-1;}
                    if(!ok) continue;
                    m2=only_b;while(m2){int ph=__builtin_ctz(m2);
                        if(in_load[dl_a][px][ph]+1>cd_max_in[dl_a][px]){ok=0;break;}m2&=m2-1;}
                } else {
                    m2=mask_a;while(m2){int ph=__builtin_ctz(m2);
                        if(in_load[dl_a][py][ph]+1>cd_max_in[dl_a][py]){ok=0;break;}m2&=m2-1;}
                    if(!ok) continue;
                    m2=mask_b;while(m2){int ph=__builtin_ctz(m2);
                        if(in_load[dl_b][px][ph]+1>cd_max_in[dl_b][px]){ok=0;break;}m2&=m2-1;}
                }
                if(!ok) continue;
                int ov_delta=0;
                m2=only_a;while(m2){int ph=__builtin_ctz(m2);
                    if(out_load[sl][py][ph]>=g_r)ov_delta++;
                    if(out_load[sl][px][ph]>g_r)ov_delta--;
                    m2&=m2-1;}
                m2=only_b;while(m2){int ph=__builtin_ctz(m2);
                    if(out_load[sl][px][ph]>=g_r)ov_delta++;
                    if(out_load[sl][py][ph]>g_r)ov_delta--;
                    m2&=m2-1;}
                if(dl_a==dl_b){
                    m2=only_a;while(m2){int ph=__builtin_ctz(m2);
                        if(in_load[dl_a][py][ph]>=g_r)ov_delta++;
                        if(in_load[dl_a][px][ph]>g_r)ov_delta--;
                        m2&=m2-1;}
                    m2=only_b;while(m2){int ph=__builtin_ctz(m2);
                        if(in_load[dl_a][px][ph]>=g_r)ov_delta++;
                        if(in_load[dl_a][py][ph]>g_r)ov_delta--;
                        m2&=m2-1;}
                } else {
                    m2=mask_a;while(m2){int ph=__builtin_ctz(m2);
                        if(in_load[dl_a][py][ph]>=g_r)ov_delta++;
                        if(in_load[dl_a][px][ph]>g_r)ov_delta--;
                        m2&=m2-1;}
                    m2=mask_b;while(m2){int ph=__builtin_ctz(m2);
                        if(in_load[dl_b][px][ph]>=g_r)ov_delta++;
                        if(in_load[dl_b][py][ph]>g_r)ov_delta--;
                        m2&=m2-1;}
                }
                int before=card_cbtphsc(ci,m)+card_cbtphsc(cj,m);
                unsigned int mk;
                mk=mask_a;while(mk){int ph=__builtin_ctz(mk);
                    cppc[ci][ph][px]--;if(!cppc[ci][ph][px])cpm[ci][ph]&=~(1u<<px);
                    cppc[ci][ph][py]++;cpm[ci][ph]|=(1u<<py);mk&=mk-1;}
                mk=mask_b;while(mk){int ph=__builtin_ctz(mk);
                    cppc[cj][ph][py]--;if(!cppc[cj][ph][py])cpm[cj][ph]&=~(1u<<py);
                    cppc[cj][ph][px]++;cpm[cj][ph]|=(1u<<px);mk&=mk-1;}
                int after=card_cbtphsc(ci,m)+card_cbtphsc(cj,m);
                int net=before-after;
                mk=mask_a;while(mk){int ph=__builtin_ctz(mk);
                    cppc[ci][ph][py]--;if(!cppc[ci][ph][py])cpm[ci][ph]&=~(1u<<py);
                    cppc[ci][ph][px]++;cpm[ci][ph]|=(1u<<px);mk&=mk-1;}
                mk=mask_b;while(mk){int ph=__builtin_ctz(mk);
                    cppc[cj][ph][px]--;if(!cppc[cj][ph][px])cpm[cj][ph]&=~(1u<<px);
                    cppc[cj][ph][py]++;cpm[cj][ph]|=(1u<<py);mk&=mk-1;}
                int wt=5*net-12*ov_delta;
                if(wt>best_wt){best_wt=wt;best_j=j;}
            }
            if(best_j<0) continue;
            {
                int j=best_j,cj=fl_src[j],dl_b=fl_dl[j];
                unsigned int mask_b=fl_pmask[j];
                unsigned int only_a=mask_a&~mask_b,only_b=mask_b&~mask_a;
                unsigned int mk,m2;
                mk=mask_a;while(mk){int ph=__builtin_ctz(mk);
                    cppc[ci][ph][px]--;if(!cppc[ci][ph][px])cpm[ci][ph]&=~(1u<<px);
                    cppc[ci][ph][py]++;cpm[ci][ph]|=(1u<<py);mk&=mk-1;}
                mk=mask_b;while(mk){int ph=__builtin_ctz(mk);
                    cppc[cj][ph][py]--;if(!cppc[cj][ph][py])cpm[cj][ph]&=~(1u<<py);
                    cppc[cj][ph][px]++;cpm[cj][ph]|=(1u<<px);mk&=mk-1;}
                m2=only_a;while(m2){int ph=__builtin_ctz(m2);
                    out_load[sl][px][ph]--;out_load[sl][py][ph]++;m2&=m2-1;}
                m2=only_b;while(m2){int ph=__builtin_ctz(m2);
                    out_load[sl][py][ph]--;out_load[sl][px][ph]++;m2&=m2-1;}
                if(dl_a==dl_b){
                    m2=only_a;while(m2){int ph=__builtin_ctz(m2);
                        in_load[dl_a][px][ph]--;in_load[dl_a][py][ph]++;m2&=m2-1;}
                    m2=only_b;while(m2){int ph=__builtin_ctz(m2);
                        in_load[dl_a][py][ph]--;in_load[dl_a][px][ph]++;m2&=m2-1;}
                } else {
                    m2=mask_a;while(m2){int ph=__builtin_ctz(m2);
                        in_load[dl_a][px][ph]--;in_load[dl_a][py][ph]++;m2&=m2-1;}
                    m2=mask_b;while(m2){int ph=__builtin_ctz(m2);
                        in_load[dl_b][py][ph]--;in_load[dl_b][px][ph]++;m2&=m2-1;}
                }
                fl_port[fi]=(short)py;fl_port[j]=(short)px;
                improved++;
            }
        }
        if(!improved) break;
    }
    // Single-flow move pass: move flows to dominant port when slack exists
    for(int iter=0;iter<2;++iter){
        for(int leaf=0;leaf<g_l;++leaf)
            for(int pk=0;pk<g_p;++pk){
                short mo=0,mi=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                    if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
                }
                cd_max_out[leaf][pk]=mo;cd_max_in[leaf][pk]=mi;
            }
        memset(cpm,0,sizeof(cpm));memset(cppc,0,sizeof(cppc));
        for(int i=0;i<fl_count;++i){
            if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
            int c=fl_src[i],p=fl_port[i];
            unsigned int mk=fl_pmask[i];
            while(mk){int ph=__builtin_ctz(mk);cppc[c][ph][p]++;cpm[c][ph]|=(1u<<p);mk&=mk-1;}
        }
        int moved=0;
        for(int fi=0;fi<fl_count;++fi){
            int sl=fl_sl[fi],dl=fl_dl[fi],px=fl_port[fi],ci=fl_src[fi];
            if(sl==dl||px<0) continue;
            if(card_cbtphsc(ci,m)==0) continue;
            int dp_cnt[32]={};
            for(int ph=0;ph<m;++ph)
                for(int pk=0;pk<g_p;++pk) dp_cnt[pk]+=cppc[ci][ph][pk];
            int dp=-1,dp_best=0;
            for(int pk=0;pk<g_p;++pk) if(dp_cnt[pk]>dp_best){dp_best=dp_cnt[pk];dp=pk;}
            if(dp<0||px==dp) continue;
            int py=dp;
            unsigned int mask=fl_pmask[fi];
            int ok=1;unsigned int m2;
            m2=mask;while(m2){int ph=__builtin_ctz(m2);
                if(out_load[sl][py][ph]+1>cd_max_out[sl][py]){ok=0;break;}m2&=m2-1;}
            if(!ok) continue;
            m2=mask;while(m2){int ph=__builtin_ctz(m2);
                if(in_load[dl][py][ph]+1>cd_max_in[dl][py]){ok=0;break;}m2&=m2-1;}
            if(!ok) continue;
            int ov_delta=0;
            m2=mask;while(m2){int ph=__builtin_ctz(m2);
                if(out_load[sl][py][ph]>=g_r)ov_delta++;
                if(out_load[sl][px][ph]>g_r)ov_delta--;
                if(in_load[dl][py][ph]>=g_r)ov_delta++;
                if(in_load[dl][px][ph]>g_r)ov_delta--;
                m2&=m2-1;}
            int before=card_cbtphsc(ci,m);
            unsigned int mk;
            mk=mask;while(mk){int ph=__builtin_ctz(mk);
                cppc[ci][ph][px]--;if(!cppc[ci][ph][px])cpm[ci][ph]&=~(1u<<px);
                cppc[ci][ph][py]++;cpm[ci][ph]|=(1u<<py);mk&=mk-1;}
            int after=card_cbtphsc(ci,m);
            int net=before-after;
            int wt=5*net-12*ov_delta;
            if(wt>0){
                mk=mask;while(mk){int ph=__builtin_ctz(mk);
                    out_load[sl][px][ph]--;out_load[sl][py][ph]++;
                    in_load[dl][px][ph]--;in_load[dl][py][ph]++;mk&=mk-1;}
                fl_port[fi]=(short)py;
                moved++;
            } else {
                mk=mask;while(mk){int ph=__builtin_ctz(mk);
                    cppc[ci][ph][py]--;if(!cppc[ci][ph][py])cpm[ci][ph]&=~(1u<<py);
                    cppc[ci][ph][px]++;cpm[ci][ph]|=(1u<<px);mk&=mk-1;}
            }
        }
        if(!moved) break;
    }
}

void run_cbttskc_reduce(int m){
    static short ct_max_out[MAX_LEAFS][MAX_PORTS];
    static short ct_max_in[MAX_LEAFS][MAX_PORTS];
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            short mo=0,mi=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
            }
            ct_max_out[leaf][pk]=mo;ct_max_in[leaf][pk]=mi;
        }
    memset(cpm,0,sizeof(cpm));memset(cppc,0,sizeof(cppc));
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
        int c=fl_src[i],p=fl_port[i];
        unsigned int mk=fl_pmask[i];
        while(mk){int ph=__builtin_ctz(mk);cppc[c][ph][p]++;cpm[c][ph]|=(1u<<p);mk&=mk-1;}
    }
    for(int iter=0;iter<3;++iter){
        int improved=0;
        for(int fi=0;fi<fl_count;++fi){
            int sl=fl_sl[fi],dl=fl_dl[fi],px=fl_port[fi],ci=fl_src[fi];
            if(sl==dl||px<0) continue;
            int cur_fo_sl=global_out[sl][px]+ct_max_out[sl][px];
            int cur_fi_dl=global_in[dl][px]+ct_max_in[dl][px];
            int cur_ct_sl=(cur_fo_sl>g_r)?(cur_fo_sl-g_r):0;
            int cur_ct_dl=(cur_fi_dl>g_r)?(cur_fi_dl-g_r):0;
            if(cur_ct_sl==0&&cur_ct_dl==0) continue;
            int at_max_out=0,at_max_in=0;
            unsigned int m2=fl_pmask[fi];
            while(m2){int ph=__builtin_ctz(m2);
                if(out_load[sl][px][ph]==ct_max_out[sl][px])at_max_out=1;
                if(in_load[dl][px][ph]==ct_max_in[dl][px])at_max_in=1;
                m2&=m2-1;}
            if(!at_max_out&&!at_max_in) continue;
            int new_max_out_px=0,new_max_in_px=0;
            if(at_max_out){
                for(int ph=0;ph<m;++ph){
                    int v=out_load[sl][px][ph]-((fl_pmask[fi]>>ph)&1);
                    if(v>new_max_out_px)new_max_out_px=v;}
            } else new_max_out_px=ct_max_out[sl][px];
            if(at_max_in){
                for(int ph=0;ph<m;++ph){
                    int v=in_load[dl][px][ph]-((fl_pmask[fi]>>ph)&1);
                    if(v>new_max_in_px)new_max_in_px=v;}
            } else new_max_in_px=ct_max_in[dl][px];
            if(new_max_out_px==ct_max_out[sl][px]&&new_max_in_px==ct_max_in[dl][px]) continue;
            int best_py=-1,best_wt=0;
            for(int py=0;py<g_p;++py){
                if(py==px) continue;
                unsigned int m3=fl_pmask[fi];
                int ok=1;
                while(m3){int ph=__builtin_ctz(m3);
                    if(out_load[sl][py][ph]+1>ct_max_out[sl][py]){ok=0;break;}
                    if(in_load[dl][py][ph]+1>ct_max_in[dl][py]){ok=0;break;}
                    m3&=m3-1;}
                if(!ok) continue;
                int new_ct_sl_px=(global_out[sl][px]+new_max_out_px>g_r)?(global_out[sl][px]+new_max_out_px-g_r):0;
                int new_ct_dl_px=(global_in[dl][px]+new_max_in_px>g_r)?(global_in[dl][px]+new_max_in_px-g_r):0;
                int ct_delta=(cur_ct_sl-new_ct_sl_px)+(cur_ct_dl-new_ct_dl_px);
                if(ct_delta<=0) continue;
                int ov_delta=0;
                m3=fl_pmask[fi];
                while(m3){int ph=__builtin_ctz(m3);
                    if(out_load[sl][py][ph]>=g_r)ov_delta++;
                    if(out_load[sl][px][ph]>g_r)ov_delta--;
                    if(in_load[dl][py][ph]>=g_r)ov_delta++;
                    if(in_load[dl][px][ph]>g_r)ov_delta--;
                    m3&=m3-1;}
                int before_cbt=card_cbtphsc(ci,m);
                unsigned int mk=fl_pmask[fi];
                while(mk){int ph=__builtin_ctz(mk);
                    cppc[ci][ph][px]--;if(!cppc[ci][ph][px])cpm[ci][ph]&=~(1u<<px);
                    cppc[ci][ph][py]++;cpm[ci][ph]|=(1u<<py);mk&=mk-1;}
                int after_cbt=card_cbtphsc(ci,m);
                mk=fl_pmask[fi];
                while(mk){int ph=__builtin_ctz(mk);
                    cppc[ci][ph][py]--;if(!cppc[ci][ph][py])cpm[ci][ph]&=~(1u<<py);
                    cppc[ci][ph][px]++;cpm[ci][ph]|=(1u<<px);mk&=mk-1;}
                int cbt_delta=before_cbt-after_cbt;
                int wt=3*ct_delta+5*cbt_delta-12*ov_delta;
                if(wt>best_wt){best_wt=wt;best_py=py;}
            }
            if(best_py<0) continue;
            {
                int py=best_py;
                unsigned int mk=fl_pmask[fi];
                while(mk){int ph=__builtin_ctz(mk);
                    cppc[ci][ph][px]--;if(!cppc[ci][ph][px])cpm[ci][ph]&=~(1u<<px);
                    cppc[ci][ph][py]++;cpm[ci][ph]|=(1u<<py);mk&=mk-1;}
                mk=fl_pmask[fi];
                while(mk){int ph=__builtin_ctz(mk);
                    out_load[sl][px][ph]--;out_load[sl][py][ph]++;
                    in_load[dl][px][ph]--;in_load[dl][py][ph]++;mk&=mk-1;}
                fl_port[fi]=(short)py;
                int nmo_px=0,nmi_px=0,nmo_py=0,nmi_py=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[sl][px][ph]>nmo_px)nmo_px=out_load[sl][px][ph];
                    if(in_load[dl][px][ph]>nmi_px)nmi_px=in_load[dl][px][ph];
                    if(out_load[sl][py][ph]>nmo_py)nmo_py=out_load[sl][py][ph];
                    if(in_load[dl][py][ph]>nmi_py)nmi_py=in_load[dl][py][ph];
                }
                ct_max_out[sl][px]=(short)nmo_px;ct_max_in[dl][px]=(short)nmi_px;
                ct_max_out[sl][py]=(short)nmo_py;ct_max_in[dl][py]=(short)nmi_py;
                improved++;
            }
        }
        if(!improved) break;
        for(int leaf=0;leaf<g_l;++leaf)
            for(int pk=0;pk<g_p;++pk){
                short mo=0,mi=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                    if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
                }
                ct_max_out[leaf][pk]=mo;ct_max_in[leaf][pk]=mi;
            }
    }
}

void run_sa_composite(int m){
    if(fl_count<10) return;
    clock_t sa_start=clock();
    double sa_budget=0.05;
    if(fl_count>5000) sa_budget=0.03;
    static short sa_max_out[MAX_LEAFS][MAX_PORTS];
    static short sa_max_in[MAX_LEAFS][MAX_PORTS];
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            short mo=0,mi=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
            }
            sa_max_out[leaf][pk]=mo;sa_max_in[leaf][pk]=mi;
        }
    memset(cpm,0,sizeof(cpm));memset(cppc,0,sizeof(cppc));
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
        int c=fl_src[i],p=fl_port[i];
        unsigned int mk=fl_pmask[i];
        while(mk){int ph=__builtin_ctz(mk);cppc[c][ph][p]++;cpm[c][ph]|=(1u<<p);mk&=mk-1;}
    }
    // Build focused list: flows from cards with CB > 0
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
    }
    // SA main loop — lower temperature for more greedy CB optimization
    double T=2.0;
    double cool=0.99995;
    unsigned int rng=fl_count*2654435761u+g_job_idx*1013904223u;
    int sa_accepted=0;
    for(int iter=0;;++iter){
        if((iter&0xFF)==0){
            double elapsed=(double)(clock()-sa_start)/CLOCKS_PER_SEC;
            if(elapsed>=sa_budget) break;
        }
        rng=rng*1664525u+1013904223u;
        int fi;
        if(sa_focus_cnt>0){
            fi=sa_focus[rng%sa_focus_cnt];
        } else {
            fi=rng%fl_count;
        }
        if(fl_sl[fi]==fl_dl[fi]||fl_port[fi]<0){T*=cool;continue;}
        int sl=fl_sl[fi],dl=fl_dl[fi],px=fl_port[fi],ci=fl_src[fi];
        rng=rng*1664525u+1013904223u;
        int py=rng%(g_p-1); if(py>=px)py++;
        unsigned int mask=fl_pmask[fi];
        unsigned int m2=mask; int ok=1;
        while(m2){int ph=__builtin_ctz(m2);
            if(out_load[sl][py][ph]+1>sa_max_out[sl][py]){ok=0;break;}
            if(in_load[dl][py][ph]+1>sa_max_in[dl][py]){ok=0;break;}
            m2&=m2-1;}
        if(!ok){T*=cool;continue;}
        int ci_delta=0;
        m2=mask;
        while(m2){int ph=__builtin_ctz(m2);
            if(out_load[sl][py][ph]>=g_r)ci_delta++;
            if(out_load[sl][px][ph]>g_r)ci_delta--;
            if(in_load[dl][py][ph]>=g_r)ci_delta++;
            if(in_load[dl][px][ph]>g_r)ci_delta--;
            m2&=m2-1;}
        int before_cbt=card_cbtphsc(ci,m);
        m2=mask;
        while(m2){int ph=__builtin_ctz(m2);
            cppc[ci][ph][px]--;if(!cppc[ci][ph][px])cpm[ci][ph]&=~(1u<<px);
            cppc[ci][ph][py]++;cpm[ci][ph]|=(1u<<py);m2&=m2-1;}
        int after_cbt=card_cbtphsc(ci,m);
        int cbt_delta=after_cbt-before_cbt;
        int obj_delta=12*ci_delta+5*cbt_delta;
        int accept=0;
        if(obj_delta<=0) accept=1;
        else{
            rng=rng*1664525u+1013904223u;
            double r=(rng&0xFFFF)/65536.0;
            if(r<__builtin_exp(-(double)obj_delta/T)) accept=1;
        }
        if(accept){
            m2=mask;
            while(m2){int ph=__builtin_ctz(m2);
                out_load[sl][px][ph]--;out_load[sl][py][ph]++;
                in_load[dl][px][ph]--;in_load[dl][py][ph]++;m2&=m2-1;}
            fl_port[fi]=(short)py;
            short nmo=0,nmi=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[sl][px][ph]>nmo)nmo=out_load[sl][px][ph];
                if(in_load[dl][px][ph]>nmi)nmi=in_load[dl][px][ph];
            }
            sa_max_out[sl][px]=nmo;sa_max_in[dl][px]=nmi;
            sa_accepted++;
        } else {
            m2=mask;
            while(m2){int ph=__builtin_ctz(m2);
                cppc[ci][ph][py]--;if(!cppc[ci][ph][py])cpm[ci][ph]&=~(1u<<py);
                cppc[ci][ph][px]++;cpm[ci][ph]|=(1u<<px);m2&=m2-1;}
        }
        T*=cool;
    }
}

static short mc_tabu[MAX_FLOWS];
static int viol_flows[13000];

static inline int collect_overflow_flows(){
    int viol_cnt=0;
    for(int i=0;i<fl_count;++i){
        int sl=fl_sl[i],dl=fl_dl[i];
        if(sl==dl) continue;
        int cp=fl_port[i];
        if(cp<0) continue;
        unsigned int mask=fl_pmask[i];
        int ov=0;
        while(mask){
            int ph=__builtin_ctz(mask);
            if(out_load[sl][cp][ph]>g_r||in_load[dl][cp][ph]>g_r){
                ov=1;
                break;
            }
            mask&=mask-1;
        }
        if(ov) viol_flows[viol_cnt++]=i;
    }
    return viol_cnt;
}

static inline void apply_flow_move(int fi,int from_pk,int to_pk){
    int sl=fl_sl[fi],dl=fl_dl[fi];
    unsigned int mask=fl_pmask[fi];
    while(mask){
        int ph=__builtin_ctz(mask);
        out_load[sl][from_pk][ph]--;
        in_load[dl][from_pk][ph]--;
        out_load[sl][to_pk][ph]++;
        in_load[dl][to_pk][ph]++;
        mask&=mask-1;
    }
    fl_port[fi]=(short)to_pk;
}

static inline int choose_lowr_repair_port(int fi,int m,unsigned int &rng,int allow_soft,
                                          int *best_delta_out=0){
    int sl=fl_sl[fi],dl=fl_dl[fi];
    int cp=fl_port[fi];
    if(sl==dl||cp<0) return -1;
    unsigned int mask=fl_pmask[fi];

    int cand_delta[32];
    int cand_local[32];
    int cand_fg[32];
    int cand_over[32];
    long long cand_sq[32];
    for(int pk=0;pk<32;++pk){
        cand_delta[pk]=0x7fffffff;
        cand_local[pk]=0x7fffffff;
        cand_fg[pk]=0x7fffffff;
        cand_over[pk]=0x7fffffff;
        cand_sq[pk]=0x7fffffffffffffffLL;
    }

    int best_pk=-1,best_delta=0x7fffffff,best_local=0x7fffffff;
    int best_fg=0x7fffffff,best_over=0x7fffffff;
    long long best_sq=0x7fffffffffffffffLL;

    for(int pk=0;pk<g_p;++pk){
        if(pk==cp) continue;
        int delta_ci=0;
        int new_out_from=0,new_out_to=0,new_in_from=0,new_in_to=0;
        for(int ph=0;ph<m;++ph){
            int take=(mask>>ph)&1u;
            int out_from=out_load[sl][cp][ph];
            int out_to=out_load[sl][pk][ph];
            int in_from=in_load[dl][cp][ph];
            int in_to=in_load[dl][pk][ph];

            if(take){
                if(out_from>g_r) delta_ci--;
                if(out_to>=g_r) delta_ci++;
                if(in_from>g_r) delta_ci--;
                if(in_to>=g_r) delta_ci++;
                out_from--;
                out_to++;
                in_from--;
                in_to++;
            }

            if(out_from>new_out_from) new_out_from=out_from;
            if(out_to>new_out_to) new_out_to=out_to;
            if(in_from>new_in_from) new_in_from=in_from;
            if(in_to>new_in_to) new_in_to=in_to;
        }

        int fo_from=global_out[sl][cp]+new_out_from;
        int fo_to=global_out[sl][pk]+new_out_to;
        int fi_from=global_in[dl][cp]+new_in_from;
        int fi_to=global_in[dl][pk]+new_in_to;

        int local_peak=new_out_from;
        if(new_out_to>local_peak) local_peak=new_out_to;
        if(new_in_from>local_peak) local_peak=new_in_from;
        if(new_in_to>local_peak) local_peak=new_in_to;

        int future_fg=fo_from;
        if(fo_to>future_fg) future_fg=fo_to;
        if(fi_from>future_fg) future_fg=fi_from;
        if(fi_to>future_fg) future_fg=fi_to;

        int future_over=0;
        if(fo_from>g_r) future_over+=(fo_from-g_r);
        if(fo_to>g_r) future_over+=(fo_to-g_r);
        if(fi_from>g_r) future_over+=(fi_from-g_r);
        if(fi_to>g_r) future_over+=(fi_to-g_r);

        long long future_sq=(long long)fo_from*fo_from+(long long)fo_to*fo_to+
                            (long long)fi_from*fi_from+(long long)fi_to*fi_to;

        cand_delta[pk]=delta_ci;
        cand_local[pk]=local_peak;
        cand_fg[pk]=future_fg;
        cand_over[pk]=future_over;
        cand_sq[pk]=future_sq;

        if(delta_ci<best_delta||
           (delta_ci==best_delta&&local_peak<best_local)||
           (delta_ci==best_delta&&local_peak==best_local&&future_fg<best_fg)||
           (delta_ci==best_delta&&local_peak==best_local&&future_fg==best_fg&&future_over<best_over)||
           (delta_ci==best_delta&&local_peak==best_local&&future_fg==best_fg&&future_over==best_over&&future_sq<best_sq)){
            best_pk=pk;
            best_delta=delta_ci;
            best_local=local_peak;
            best_fg=future_fg;
            best_over=future_over;
            best_sq=future_sq;
        }
    }

    if(best_delta_out) *best_delta_out=best_delta;
    if(best_pk<0||!allow_soft) return best_pk;

    int soft_pks[32];
    int soft_cnt=0;
    for(int pk=0;pk<g_p;++pk){
        if(pk==cp) continue;
        if(cand_delta[pk]>best_delta+1) continue;
        if(cand_local[pk]>best_local+1) continue;
        if(cand_fg[pk]>best_fg+1) continue;
        if(cand_over[pk]>best_over+2) continue;
        soft_pks[soft_cnt++]=pk;
    }
    if(soft_cnt>1){
        rng=rng*1664525u+1013904223u;
        best_pk=soft_pks[(rng>>16)%soft_cnt];
        if(best_delta_out) *best_delta_out=cand_delta[best_pk];
    }
    return best_pk;
}

static int core_cards[MAX_CARDS];
static int core_card_score[MAX_CARDS];
static unsigned char core_card_seen[MAX_CARDS];
static int cell_core_score[MAX_FLOWS];
static unsigned char cell_core_seen[MAX_FLOWS];

struct LowrHotCell{
    short leaf;
    short port;
    short ph;
    unsigned char dir;
    short load;
    int score;
};

static inline void insert_hot_cell(LowrHotCell *cells,int &cnt,int cap,
                                   int leaf,int port,int ph,int dir,int load,int score){
    if(cnt<cap){
        cells[cnt].leaf=(short)leaf;
        cells[cnt].port=(short)port;
        cells[cnt].ph=(short)ph;
        cells[cnt].dir=(unsigned char)dir;
        cells[cnt].load=(short)load;
        cells[cnt].score=score;
        cnt++;
    } else if(score<=cells[cnt-1].score){
        return;
    } else {
        cells[cnt-1].leaf=(short)leaf;
        cells[cnt-1].port=(short)port;
        cells[cnt-1].ph=(short)ph;
        cells[cnt-1].dir=(unsigned char)dir;
        cells[cnt-1].load=(short)load;
        cells[cnt-1].score=score;
    }
    for(int i=cnt-1;i>0&&cells[i].score>cells[i-1].score;--i){
        LowrHotCell t=cells[i];
        cells[i]=cells[i-1];
        cells[i-1]=t;
    }
}

static inline int lowr_core_flow_priority(int fi){
    int sl=fl_sl[fi],dl=fl_dl[fi],cp=fl_port[fi];
    int ov_hits=0;
    unsigned int mask=fl_pmask[fi];
    while(mask){
        int ph=__builtin_ctz(mask);
        if(bk_out[sl][cp][ph]>g_r) ov_hits+=2;
        if(bk_in[dl][cp][ph]>g_r) ov_hits+=2;
        mask&=mask-1;
    }
    return ov_hits*128+__builtin_popcount(fl_pmask[fi])*8;
}

static inline int lowr_job_jm_lower_bound(int m){
    short phase_out[MAX_LEAFS][MAX_PHASES];
    short phase_in[MAX_LEAFS][MAX_PHASES];
    memset(phase_out,0,sizeof(phase_out));
    memset(phase_in,0,sizeof(phase_in));
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]) continue;
        int sl=fl_sl[i],dl=fl_dl[i];
        unsigned int mask=fl_pmask[i];
        while(mask){
            int ph=__builtin_ctz(mask);
            phase_out[sl][ph]++;
            phase_in[dl][ph]++;
            mask&=mask-1;
        }
    }
    int lb=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int ph=0;ph<m;++ph){
            int o=phase_out[leaf][ph];
            int iv=phase_in[leaf][ph];
            int lo=(o+g_p-1)/g_p;
            int li=(iv+g_p-1)/g_p;
            if(lo>lb) lb=lo;
            if(li>lb) lb=li;
        }
    return lb;
}

static inline int lowr_future_fg_lower_bound(int m){
    short phase_out[MAX_LEAFS][MAX_PHASES];
    short phase_in[MAX_LEAFS][MAX_PHASES];
    short leaf_outmax[MAX_LEAFS];
    short leaf_inmax[MAX_LEAFS];
    int global_leaf_out[MAX_LEAFS];
    int global_leaf_in[MAX_LEAFS];
    memset(phase_out,0,sizeof(phase_out));
    memset(phase_in,0,sizeof(phase_in));
    memset(leaf_outmax,0,sizeof(leaf_outmax));
    memset(leaf_inmax,0,sizeof(leaf_inmax));
    memset(global_leaf_out,0,sizeof(global_leaf_out));
    memset(global_leaf_in,0,sizeof(global_leaf_in));
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            global_leaf_out[leaf]+=global_out[leaf][pk];
            global_leaf_in[leaf]+=global_in[leaf][pk];
        }
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]) continue;
        int sl=fl_sl[i],dl=fl_dl[i];
        unsigned int mask=fl_pmask[i];
        while(mask){
            int ph=__builtin_ctz(mask);
            phase_out[sl][ph]++;
            phase_in[dl][ph]++;
            mask&=mask-1;
        }
    }
    for(int leaf=0;leaf<g_l;++leaf)
        for(int ph=0;ph<m;++ph){
            if(phase_out[leaf][ph]>leaf_outmax[leaf]) leaf_outmax[leaf]=phase_out[leaf][ph];
            if(phase_in[leaf][ph]>leaf_inmax[leaf]) leaf_inmax[leaf]=phase_in[leaf][ph];
        }
    int lb=0;
    for(int leaf=0;leaf<g_l;++leaf){
        int lo=(global_leaf_out[leaf]+leaf_outmax[leaf]+g_p-1)/g_p;
        int li=(global_leaf_in[leaf]+leaf_inmax[leaf]+g_p-1)/g_p;
        if(lo>lb) lb=lo;
        if(li>lb) lb=li;
    }
    return lb;
}

__attribute__((noinline,cold)) void run_lowr_hotcell_exact(int m){
    if(g_r>3||g_p<16) return;
    if(fl_count>2500||(long long)fl_count*m>50000) return;

    EvalMetrics base_eval=collect_metrics(m);
    if(base_eval.jm<=g_r) return;
    int lb_jm=lowr_job_jm_lower_bound(m);
    if(base_eval.jm<=lb_jm) return;

    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));

    EvalMetrics best_eval=base_eval;
    int improved=0;

    for(int round=0;round<4;++round){
        int best_move_fi=-1,best_move_pk=-1;
        EvalMetrics round_best=best_eval;

        for(int fi=0;fi<fl_count;++fi){
            int cp=fl_port[fi];
            if(cp<0||fl_sl[fi]==fl_dl[fi]) continue;

            int sl=fl_sl[fi],dl=fl_dl[fi];
            unsigned int mask=fl_pmask[fi];
            int touches_hot=0;
            unsigned int mk=mask;
            while(mk){
                int ph=__builtin_ctz(mk);
                if(out_load[sl][cp][ph]==best_eval.jm||in_load[dl][cp][ph]==best_eval.jm){
                    touches_hot=1;
                    break;
                }
                mk&=mk-1;
            }
            if(!touches_hot) continue;

            for(int pk=0;pk<g_p;++pk){
                if(pk==cp) continue;
                int ok=1;
                mk=mask;
                while(mk){
                    int ph=__builtin_ctz(mk);
                    if(out_load[sl][pk][ph]+1>g_r||in_load[dl][pk][ph]+1>g_r){
                        ok=0;
                        break;
                    }
                    mk&=mk-1;
                }
                if(!ok) continue;

                apply_flow_move(fi,cp,pk);
                EvalMetrics cand_eval=collect_metrics(m);
                apply_flow_move(fi,pk,cp);

                if(better_metrics(cand_eval,round_best)){
                    round_best=cand_eval;
                    best_move_fi=fi;
                    best_move_pk=pk;
                }
            }
        }

        if(best_move_fi<0) break;
        apply_flow_move(best_move_fi,fl_port[best_move_fi],best_move_pk);
        best_eval=round_best;
        improved=1;
        if(best_eval.jm<=g_r) break;
    }

    if(!improved||!better_metrics(best_eval,base_eval)){
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

__attribute__((noinline,cold)) void run_lowr_hotleaf_rebuild(int m){
    if(g_r>3||g_p<16) return;
    if(fl_count>4500||(long long)fl_count*m>70000) return;

    EvalMetrics base_eval=collect_metrics(m);
    if(base_eval.fg<=g_r) return;
    if(base_eval.fg<=lowr_future_fg_lower_bound(m)) return;

    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));

    int best_dir=-1,best_leaf=-1,best_top=-1,best_sum4=-1;
    int best_ports[32];
    memset(best_ports,0,sizeof(best_ports));
    for(int dir=0;dir<2;++dir){
        for(int leaf=0;leaf<g_l;++leaf){
            int vals[32];
            int top=0,sum4=0;
            for(int pk=0;pk<g_p;++pk){
                int local=0;
                for(int ph=0;ph<m;++ph){
                    int cur=(dir==0)?out_load[leaf][pk][ph]:in_load[leaf][pk][ph];
                    if(cur>local) local=cur;
                }
                vals[pk]=((dir==0)?global_out[leaf][pk]:global_in[leaf][pk])+local;
            }
            for(int a=0;a<g_p;++a){
                int best=a;
                for(int b=a+1;b<g_p;++b)
                    if(vals[b]>vals[best]) best=b;
                if(best!=a){
                    int tv=vals[a];vals[a]=vals[best];vals[best]=tv;
                }
            }
            top=vals[0];
            for(int i=0;i<g_p&&i<4;++i) sum4+=vals[i];
            if(top>best_top||(top==best_top&&sum4>best_sum4)){
                best_top=top;best_sum4=sum4;best_dir=dir;best_leaf=leaf;
                for(int pk=0;pk<g_p;++pk){
                    int local=0;
                    for(int ph=0;ph<m;++ph){
                        int cur=(dir==0)?out_load[leaf][pk][ph]:in_load[leaf][pk][ph];
                        if(cur>local) local=cur;
                    }
                    best_ports[pk]=((dir==0)?global_out[leaf][pk]:global_in[leaf][pk])+local;
                }
            }
        }
    }
    if(best_dir<0||best_top<base_eval.fg) return;

    int cnt=0;
    for(int i=0;i<fl_count;++i){
        if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
        if((best_dir==0&&fl_sl[i]!=best_leaf)||(best_dir==1&&fl_dl[i]!=best_leaf)) continue;
        pc_flows[cnt++]=i;
    }
    if(cnt<=1) return;

    for(int i=0;i<cnt;++i){
        int fi=pc_flows[i];
        int cp=bk_port[fi];
        cell_core_score[fi]=best_ports[cp]*256+__builtin_popcount(fl_pmask[fi])*8;
    }
    for(int i=0;i<cnt;++i){
        int best=i;
        for(int j=i+1;j<cnt;++j)
            if(cell_core_score[pc_flows[j]]>cell_core_score[pc_flows[best]])
                best=j;
        if(best!=i){
            int t=pc_flows[i];
            pc_flows[i]=pc_flows[best];
            pc_flows[best]=t;
        }
    }
    if(cnt>128) cnt=128;

    memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
    memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
    memcpy(fl_port, bk_port, fl_count*sizeof(short));

    for(int i=0;i<cnt;++i){
        int fi=pc_flows[i];
        int sl=fl_sl[fi],dl=fl_dl[fi],cp=fl_port[fi];
        unsigned int mask=fl_pmask[fi];
        while(mask){
            int ph=__builtin_ctz(mask);
            out_load[sl][cp][ph]--;
            in_load[dl][cp][ph]--;
            mask&=mask-1;
        }
    }

    for(int i=0;i<cnt;++i){
        int fi=pc_flows[i];
        int sl=fl_sl[fi],dl=fl_dl[fi],cur_pk=bk_port[fi];
        unsigned int mask=fl_pmask[fi];
        int best_pk=0,best_local=0x7fffffff,best_hot=0x7fffffff,best_add_over=0x7fffffff;
        int best_other=0x7fffffff,best_press=0x7fffffff,best_change=0x7fffffff;
        for(int pk=0;pk<g_p;++pk){
            int local_peak=0,add_over=0;
            unsigned int mk=mask;
            while(mk){
                int ph=__builtin_ctz(mk);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                if(o>local_peak) local_peak=o;
                if(iv>local_peak) local_peak=iv;
                if(out_load[sl][pk][ph]>=g_r) add_over++;
                if(in_load[dl][pk][ph]>=g_r) add_over++;
                mk&=mk-1;
            }
            int hot_m=0,other_m=0;
            for(int ph=0;ph<m;++ph){
                int hot_cur,other_cur;
                if(best_dir==0){
                    hot_cur=(sl==best_leaf)?out_load[sl][pk][ph]+((mask>>ph)&1u):out_load[best_leaf][pk][ph];
                    other_cur=in_load[dl][pk][ph]+((mask>>ph)&1u);
                } else {
                    hot_cur=(dl==best_leaf)?in_load[dl][pk][ph]+((mask>>ph)&1u):in_load[best_leaf][pk][ph];
                    other_cur=out_load[sl][pk][ph]+((mask>>ph)&1u);
                }
                if(hot_cur>hot_m) hot_m=hot_cur;
                if(other_cur>other_m) other_m=other_cur;
            }
            int hot_future=((best_dir==0)?global_out[best_leaf][pk]:global_in[best_leaf][pk])+hot_m;
            int other_future=((best_dir==0)?global_in[dl][pk]:global_out[sl][pk])+other_m;
            int press=global_out[sl][pk]+global_in[dl][pk];
            int change=(pk!=cur_pk);
            if(local_peak<best_local||
               (local_peak==best_local&&hot_future<best_hot)||
               (local_peak==best_local&&hot_future==best_hot&&add_over<best_add_over)||
               (local_peak==best_local&&hot_future==best_hot&&add_over==best_add_over&&other_future<best_other)||
               (local_peak==best_local&&hot_future==best_hot&&add_over==best_add_over&&other_future==best_other&&press<best_press)||
               (local_peak==best_local&&hot_future==best_hot&&add_over==best_add_over&&other_future==best_other&&press==best_press&&change<best_change)){
                best_local=local_peak;
                best_hot=hot_future;
                best_add_over=add_over;
                best_other=other_future;
                best_press=press;
                best_change=change;
                best_pk=pk;
            }
        }
        fl_port[fi]=(short)best_pk;
        unsigned int mk=mask;
        while(mk){
            int ph=__builtin_ctz(mk);
            out_load[sl][best_pk][ph]++;
            in_load[dl][best_pk][ph]++;
            mk&=mk-1;
        }
    }

    EvalMetrics cand_eval=collect_metrics(m);
    if(better_metrics(cand_eval,base_eval)){
        memcpy(sv_out, out_load, g_l*sizeof(out_load[0]));
        memcpy(sv_in, in_load, g_l*sizeof(in_load[0]));
        memcpy(sv_port, fl_port, fl_count*sizeof(short));
        memcpy(out_load, sv_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, sv_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, sv_port, fl_count*sizeof(short));
    } else {
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

__attribute__((noinline,cold)) void run_lowr_cell_core_rebuild(int m){
    if(g_r>3||g_p<16) return;
    if(fl_count>4500||(long long)fl_count*m>70000) return;

    EvalMetrics base_eval=collect_metrics(m);
    if(base_eval.jm<=g_r||base_eval.jm>g_r+1) return;
    if(base_eval.jm<=lowr_job_jm_lower_bound(m)) return;

    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));

    LowrHotCell hot_cells[16];
    int hot_cnt=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk)
            for(int ph=0;ph<m;++ph){
                int o=bk_out[leaf][pk][ph];
                if(o>g_r){
                    int score=(o-g_r)*8192+(o==base_eval.jm?4096:0)+
                              (global_out[leaf][pk]+o)*16;
                    insert_hot_cell(hot_cells,hot_cnt,16,leaf,pk,ph,0,o,score);
                }
                int iv=bk_in[leaf][pk][ph];
                if(iv>g_r){
                    int score=(iv-g_r)*8192+(iv==base_eval.jm?4096:0)+
                              (global_in[leaf][pk]+iv)*16;
                    insert_hot_cell(hot_cells,hot_cnt,16,leaf,pk,ph,1,iv,score);
                }
            }
    if(hot_cnt<=0) return;

    EvalMetrics best_eval=base_eval;
    int improved=0;
    int max_use_cells=hot_cnt<(g_r==2?4:6)?hot_cnt:(g_r==2?4:6);

    for(int use_cells=1;use_cells<=max_use_cells;++use_cells){
        int core_cnt=0;
        for(int ci=0;ci<use_cells;++ci){
            LowrHotCell hc=hot_cells[ci];
            for(int fi=0;fi<fl_count;++fi){
                if(bk_port[fi]!=hc.port) continue;
                int hit=0;
                if(hc.dir==0){
                    if(fl_sl[fi]==hc.leaf&&((fl_pmask[fi]>>hc.ph)&1u)) hit=1;
                } else {
                    if(fl_dl[fi]==hc.leaf&&((fl_pmask[fi]>>hc.ph)&1u)) hit=1;
                }
                if(!hit) continue;
                cell_core_score[fi]+=hc.score+64;
                if(!cell_core_seen[fi]){
                    cell_core_seen[fi]=1;
                    pc_flows[core_cnt++]=fi;
                }
            }
        }
        if(core_cnt<=1){
            for(int i=0;i<core_cnt;++i){
                int fi=pc_flows[i];
                cell_core_seen[fi]=0;
                cell_core_score[fi]=0;
            }
            continue;
        }

        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));

        for(int i=0;i<core_cnt;++i){
            int fi=pc_flows[i];
            int sl=fl_sl[fi],dl=fl_dl[fi],cp=fl_port[fi];
            unsigned int mask=fl_pmask[fi];
            while(mask){
                int ph=__builtin_ctz(mask);
                out_load[sl][cp][ph]--;
                in_load[dl][cp][ph]--;
                mask&=mask-1;
            }
        }

        for(int i=0;i<core_cnt;++i){
            int best=i;
            for(int j=i+1;j<core_cnt;++j){
                int fj=pc_flows[j],fb=pc_flows[best];
                if(cell_core_score[fj]>cell_core_score[fb]||
                   (cell_core_score[fj]==cell_core_score[fb]&&
                    __builtin_popcount(fl_pmask[fj])>__builtin_popcount(fl_pmask[fb]))){
                    best=j;
                }
            }
            if(best!=i){
                int t=pc_flows[i];
                pc_flows[i]=pc_flows[best];
                pc_flows[best]=t;
            }
        }

        for(int i=0;i<core_cnt;++i){
            int fi=pc_flows[i];
            int sl=fl_sl[fi],dl=fl_dl[fi];
            int cur_pk=bk_port[fi];
            unsigned int mask=fl_pmask[fi];

            int best_pk=0,best_local=0x7fffffff,best_add_over=0x7fffffff;
            int best_hot=0x7fffffff,best_fg=0x7fffffff,best_press=0x7fffffff;
            int best_change=0x7fffffff;

            for(int pk=0;pk<g_p;++pk){
                int local_peak=0,add_over=0,hot_hits=0;
                unsigned int mk=mask;
                while(mk){
                    int ph=__builtin_ctz(mk);
                    int o=out_load[sl][pk][ph]+1;
                    int iv=in_load[dl][pk][ph]+1;
                    if(o>local_peak) local_peak=o;
                    if(iv>local_peak) local_peak=iv;
                    if(out_load[sl][pk][ph]>=g_r) add_over++;
                    if(in_load[dl][pk][ph]>=g_r) add_over++;
                    for(int ci=0;ci<use_cells;++ci){
                        if(hot_cells[ci].port!=pk||hot_cells[ci].ph!=ph) continue;
                        if(hot_cells[ci].dir==0&&hot_cells[ci].leaf==sl) hot_hits++;
                        if(hot_cells[ci].dir==1&&hot_cells[ci].leaf==dl) hot_hits++;
                    }
                    mk&=mk-1;
                }

                int mo=0,mi=0;
                for(int ph=0;ph<m;++ph){
                    int o=out_load[sl][pk][ph]+((mask>>ph)&1u);
                    int iv=in_load[dl][pk][ph]+((mask>>ph)&1u);
                    if(o>mo) mo=o;
                    if(iv>mi) mi=iv;
                }
                int future_fg=global_out[sl][pk]+mo;
                int fi_fg=global_in[dl][pk]+mi;
                if(fi_fg>future_fg) future_fg=fi_fg;
                int press=global_out[sl][pk]+global_in[dl][pk];
                int change=(pk!=cur_pk);

                if(local_peak<best_local||
                   (local_peak==best_local&&add_over<best_add_over)||
                   (local_peak==best_local&&add_over==best_add_over&&hot_hits<best_hot)||
                   (local_peak==best_local&&add_over==best_add_over&&hot_hits==best_hot&&future_fg<best_fg)||
                   (local_peak==best_local&&add_over==best_add_over&&hot_hits==best_hot&&future_fg==best_fg&&press<best_press)||
                   (local_peak==best_local&&add_over==best_add_over&&hot_hits==best_hot&&future_fg==best_fg&&press==best_press&&change<best_change)){
                    best_local=local_peak;
                    best_add_over=add_over;
                    best_hot=hot_hits;
                    best_fg=future_fg;
                    best_press=press;
                    best_change=change;
                    best_pk=pk;
                }
            }

            fl_port[fi]=(short)best_pk;
            unsigned int mk=mask;
            while(mk){
                int ph=__builtin_ctz(mk);
                out_load[sl][best_pk][ph]++;
                in_load[dl][best_pk][ph]++;
                mk&=mk-1;
            }
        }

        EvalMetrics cand_eval=collect_metrics(m);
        if(better_metrics(cand_eval,best_eval)){
            best_eval=cand_eval;
            improved=1;
            memcpy(sv_out, out_load, g_l*sizeof(out_load[0]));
            memcpy(sv_in, in_load, g_l*sizeof(in_load[0]));
            memcpy(sv_port, fl_port, fl_count*sizeof(short));
        }

        for(int i=0;i<core_cnt;++i){
            int fi=pc_flows[i];
            cell_core_seen[fi]=0;
            cell_core_score[fi]=0;
        }
    }

    if(improved){
        memcpy(out_load, sv_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, sv_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, sv_port, fl_count*sizeof(short));
    } else {
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

__attribute__((noinline,cold)) void run_lowr_card_core_rebuild(int m){
    if(g_r>3||g_p<16) return;
    if(fl_count>4500||(long long)fl_count*m>70000) return;

    EvalMetrics base_eval=collect_metrics(m);
    if(base_eval.jm<=g_r||base_eval.jm>g_r+1) return;

    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));

    int viol_cnt=collect_overflow_flows();
    if(viol_cnt<=0) return;

    int cand_cnt=0;
    for(int i=0;i<viol_cnt;++i){
        int fi=viol_flows[i];
        int c=fl_src[fi];
        if(!core_card_seen[c]){
            core_card_seen[c]=1;
            core_card_score[c]=0;
            core_cards[cand_cnt++]=c;
        }
        core_card_score[c]+=lowr_core_flow_priority(fi);
    }
    for(int i=0;i<cand_cnt;++i) core_card_seen[core_cards[i]]=0;

    for(int i=0;i<cand_cnt;++i){
        int best=i;
        for(int j=i+1;j<cand_cnt;++j)
            if(core_card_score[core_cards[j]]>core_card_score[core_cards[best]])
                best=j;
        if(best!=i){
            int t=core_cards[i];
            core_cards[i]=core_cards[best];
            core_cards[best]=t;
        }
    }

    EvalMetrics best_eval=base_eval;
    int improved=0;
    int max_cards=(g_r==2)?3:5;
    if(cand_cnt<max_cards) max_cards=cand_cnt;

    for(int ci=0;ci<max_cards;++ci){
        int src_card=core_cards[ci];
        int cnt=0;
        for(int i=0;i<fl_count;++i){
            if(fl_src[i]==src_card&&fl_sl[i]!=fl_dl[i]&&fl_port[i]>=0)
                pc_flows[cnt++]=i;
        }
        if(cnt<=1||cnt>96) continue;

        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));

        for(int i=0;i<cnt;++i){
            int fi=pc_flows[i];
            int sl=fl_sl[fi],dl=fl_dl[fi],cp=fl_port[fi];
            unsigned int mask=fl_pmask[fi];
            while(mask){
                int ph=__builtin_ctz(mask);
                out_load[sl][cp][ph]--;
                in_load[dl][cp][ph]--;
                mask&=mask-1;
            }
        }

        for(int i=0;i<cnt;++i){
            int best=i;
            for(int j=i+1;j<cnt;++j)
                if(lowr_core_flow_priority(pc_flows[j])>lowr_core_flow_priority(pc_flows[best]))
                    best=j;
            if(best!=i){
                int t=pc_flows[i];
                pc_flows[i]=pc_flows[best];
                pc_flows[best]=t;
            }
        }

        unsigned int src_masks[MAX_PHASES]={};
        for(int i=0;i<cnt;++i){
            int fi=pc_flows[i];
            int sl=fl_sl[fi],dl=fl_dl[fi];
            int cur_pk=bk_port[fi];
            unsigned int mask=fl_pmask[fi];

            int best_pk=0,best_local=0x7fffffff,best_add_over=0x7fffffff;
            int best_cbt=0x7fffffff,best_fg=0x7fffffff,best_press=0x7fffffff;
            int best_change=0x7fffffff;

            for(int pk=0;pk<g_p;++pk){
                int local_peak=0,add_over=0;
                unsigned int tmp_masks[MAX_PHASES];
                memcpy(tmp_masks,src_masks,m*sizeof(unsigned int));
                unsigned int mk=mask;
                while(mk){
                    int ph=__builtin_ctz(mk);
                    int o=out_load[sl][pk][ph]+1;
                    int iv=in_load[dl][pk][ph]+1;
                    if(o>local_peak) local_peak=o;
                    if(iv>local_peak) local_peak=iv;
                    if(out_load[sl][pk][ph]>=g_r) add_over++;
                    if(in_load[dl][pk][ph]>=g_r) add_over++;
                    tmp_masks[ph]|=(1u<<pk);
                    mk&=mk-1;
                }

                int after_cbt=calc_phase_mask_cbt(tmp_masks,m);
                int mo=0,mi=0;
                for(int ph=0;ph<m;++ph){
                    int o=out_load[sl][pk][ph]+((mask>>ph)&1u);
                    int iv=in_load[dl][pk][ph]+((mask>>ph)&1u);
                    if(o>mo) mo=o;
                    if(iv>mi) mi=iv;
                }
                int future_fg=global_out[sl][pk]+mo;
                int fi_fg=global_in[dl][pk]+mi;
                if(fi_fg>future_fg) future_fg=fi_fg;
                int press=global_out[sl][pk]+global_in[dl][pk];
                int change=(pk!=cur_pk);

                if(local_peak<best_local||
                   (local_peak==best_local&&add_over<best_add_over)||
                   (local_peak==best_local&&add_over==best_add_over&&after_cbt<best_cbt)||
                   (local_peak==best_local&&add_over==best_add_over&&after_cbt==best_cbt&&future_fg<best_fg)||
                   (local_peak==best_local&&add_over==best_add_over&&after_cbt==best_cbt&&future_fg==best_fg&&press<best_press)||
                   (local_peak==best_local&&add_over==best_add_over&&after_cbt==best_cbt&&future_fg==best_fg&&press==best_press&&change<best_change)){
                    best_local=local_peak;
                    best_add_over=add_over;
                    best_cbt=after_cbt;
                    best_fg=future_fg;
                    best_press=press;
                    best_change=change;
                    best_pk=pk;
                }
            }

            fl_port[fi]=(short)best_pk;
            unsigned int mk=mask;
            while(mk){
                int ph=__builtin_ctz(mk);
                out_load[sl][best_pk][ph]++;
                in_load[dl][best_pk][ph]++;
                src_masks[ph]|=(1u<<best_pk);
                mk&=mk-1;
            }
        }

        EvalMetrics cand_eval=collect_metrics(m);
        if(better_metrics(cand_eval,best_eval)){
            best_eval=cand_eval;
            improved=1;
            memcpy(sv_out, out_load, g_l*sizeof(out_load[0]));
            memcpy(sv_in, in_load, g_l*sizeof(in_load[0]));
            memcpy(sv_port, fl_port, fl_count*sizeof(short));
        }
    }

    if(improved){
        memcpy(out_load, sv_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, sv_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, sv_port, fl_count*sizeof(short));
    } else {
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

void run_mc_repair(int m){
    int orig_max=get_job_max(m);
    if(orig_max<=g_r||orig_max>g_r+2) return;
    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));
    int viol_cnt=0;
    for(int i=0;i<fl_count;++i){
        mc_tabu[i]=0;
        int sl=fl_sl[i],dl=fl_dl[i];
        if(sl==dl) continue;
        int cp=fl_port[i]; if(cp<0) continue;
        unsigned int m2=fl_pmask[i]; int on_ov=0;
        while(m2){int ph=__builtin_ctz(m2);
            if(out_load[sl][cp][ph]>g_r||in_load[dl][cp][ph]>g_r)
                {on_ov=1;break;}
            m2&=m2-1;}
        if(on_ov) viol_flows[viol_cnt++]=i;
    }
    unsigned int rng=viol_cnt*31+m*7+fl_count*13;
    int no_progress=0;
    for(int iter=0;iter<3000&&viol_cnt>0;++iter){
        if(no_progress>300) break;
        rng=rng*1664525u+1013904223u;
        int fi=viol_flows[rng%viol_cnt];
        if(mc_tabu[fi]>iter){no_progress++;continue;}
        int sl=fl_sl[fi],dl=fl_dl[fi],cp=fl_port[fi];
        unsigned int mask=fl_pmask[fi];
        int best_pk=-1,best_delta=1,n_best=0;
        static int best_pks[32];
        for(int pk=0;pk<g_p;++pk){
            if(pk==cp) continue;
            int delta=0; unsigned int m2=mask;
            while(m2){int ph=__builtin_ctz(m2);
                if(out_load[sl][cp][ph]>g_r) delta--;
                if(out_load[sl][pk][ph]>=g_r) delta++;
                if(in_load[dl][cp][ph]>g_r) delta--;
                if(in_load[dl][pk][ph]>=g_r) delta++;
                m2&=m2-1;}
            if(delta<best_delta){
                best_delta=delta;n_best=0;best_pks[n_best++]=pk;
            } else if(delta==best_delta&&n_best<32){
                best_pks[n_best++]=pk;
            }
        }
        if(best_delta<=0&&n_best>0){
            rng=rng*1664525u+1013904223u;
            best_pk=best_pks[rng%n_best];
            unsigned int m2=mask;
            while(m2){int ph=__builtin_ctz(m2);
                out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;
                out_load[sl][best_pk][ph]++;in_load[dl][best_pk][ph]++;
                m2&=m2-1;}
            fl_port[fi]=(short)best_pk;
            mc_tabu[fi]=(short)(iter+10);
            int prev_vc=viol_cnt;
            viol_cnt=collect_overflow_flows();
            if(viol_cnt<prev_vc) no_progress=0;
            else no_progress++;
        } else { no_progress++; }
    }
    if(get_job_max(m)>=orig_max){
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

__attribute__((noinline,cold)) void run_random_start_repair(int m){
    EvalMetrics base_eval=collect_metrics(m);
    if(base_eval.jm<=g_r) return;
    if(base_eval.jm!=g_r+1) return;
    memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
    memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
    memcpy(bk_port, fl_port, fl_count*sizeof(short));
    int base_viol_cnt=collect_overflow_flows();
    if(base_viol_cnt<=0) return;

    EvalMetrics best_eval=base_eval;
    int improved=0;
    unsigned int rng_seed=fl_count*97+m*31+g_p*13+g_r*7;
    int strong_lowr=(g_r==2&&g_p>=32);
    int n_restarts=strong_lowr?((fl_count<=1500)?28:18):((fl_count<=1000)?18:((fl_count<=2500)?12:8));

    for(int restart=0;restart<n_restarts;++restart){
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));

        for(int i=0;i<fl_count;++i) mc_tabu[i]=0;

        rng_seed=rng_seed*1664525u+1013904223u;
        unsigned int rng=rng_seed+restart*999983u;

        int perturb_budget=base_viol_cnt/2+2+(restart&3);
        if(strong_lowr) perturb_budget+=2+(restart&1);
        if(perturb_budget>(strong_lowr?32:24)) perturb_budget=strong_lowr?32:24;
        if(perturb_budget>base_viol_cnt) perturb_budget=base_viol_cnt;

        int offset=base_viol_cnt?((rng>>16)%base_viol_cnt):0;
        for(int step=0;step<perturb_budget;++step){
            int fi=viol_flows[(offset+step)%base_viol_cnt];
            if(fl_sl[fi]==fl_dl[fi]) continue;
            int cp=fl_port[fi];
            if(cp<0) continue;
            int best_delta=0;
            int pk=choose_lowr_repair_port(fi,m,rng,1,&best_delta);
            if(pk<0||pk==cp) continue;
            apply_flow_move(fi,cp,pk);
            mc_tabu[fi]=(short)(step+4);
        }

        int viol_cnt=collect_overflow_flows();
        int best_viol_cnt=viol_cnt;
        int no_progress=0;
        int iter_cap=800+base_viol_cnt*35;
        if(strong_lowr) iter_cap+=300+base_viol_cnt*10;
        if(iter_cap>(strong_lowr?3200:2200)) iter_cap=strong_lowr?3200:2200;
        for(int iter=0;iter<iter_cap&&viol_cnt>0;++iter){
            if(no_progress>(strong_lowr?220:150)+base_viol_cnt*(strong_lowr?4:3)) break;
            rng=rng*1664525u+1013904223u;
            int fi=viol_flows[rng%viol_cnt];
            if(mc_tabu[fi]>iter){no_progress++;continue;}
            int cp=fl_port[fi];
            if(cp<0){no_progress++;continue;}
            int best_delta=0;
            int pk=choose_lowr_repair_port(fi,m,rng,0,&best_delta);
            if(pk>=0&&pk!=cp&&best_delta<=0){
                apply_flow_move(fi,cp,pk);
                mc_tabu[fi]=(short)(iter+8);
                viol_cnt=collect_overflow_flows();
                if(viol_cnt<best_viol_cnt){
                    best_viol_cnt=viol_cnt;
                    no_progress=0;
                } else {
                    no_progress++;
                }
            } else {
                no_progress++;
            }
        }

        EvalMetrics cand_eval=collect_metrics(m);
        if(better_metrics(cand_eval,best_eval)){
            best_eval=cand_eval;
            improved=1;
            memcpy(sv_out, out_load, g_l*sizeof(out_load[0]));
            memcpy(sv_in, in_load, g_l*sizeof(in_load[0]));
            memcpy(sv_port, fl_port, fl_count*sizeof(short));
            if(best_eval.jm<=g_r&&best_eval.fg<=base_eval.fg) break;
        }
    }

    if(improved){
        memcpy(out_load, sv_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, sv_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, sv_port, fl_count*sizeof(short));
    } else {
        memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
        memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
        memcpy(fl_port, bk_port, fl_count*sizeof(short));
    }
}

void solve_job(){
    int m=fast_read_int(),f=fast_read_int();
    fl_count=0; ht_clear();
    for(int ph=0;ph<m;++ph)
        for(int i=0;i<f;++i){
            int src=fast_read_int(),dst=fast_read_int();
            int hi=src*MAX_CARDS+dst,by=hi>>3,bi=hi&7;
            if(!(seen_bits[by]&(1<<bi))){
                seen_bits[by]|=(1<<bi);
                fl_src[fl_count]=src;fl_dst[fl_count]=dst;
                fl_pmask[fl_count]=(1u<<ph);
                ht_insert(hi,fl_count);
                fl_count++;
            } else {
                int fi=ht_find(hi);
                fl_pmask[fi]|=(1u<<ph);
            }
        }
    for(int i=0;i<ht_used_cnt;++i){int hi=ht_key[ht_used[i]];seen_bits[hi>>3]&=~(1<<(hi&7));}
    for(int i=0;i<fl_count;++i){
        fl_sl[i]=fl_src[i]/g_pr;
        fl_dl[i]=fl_dst[i]/g_pr;
        fl_order[i]=i;
    }

    long long job_work = (long long)fl_count * (long long)m;
    int huge_job = job_work > 150000;
    int time_tight = 0;
    if(g_job_idx>0){
        double el=elapsed_sec();
        double proj=el/g_job_idx*g_n;
        if(proj>4.5) time_tight=1;
        if(el>3.0&&fl_count>20000) time_tight=1;
    }
    g_time_tight=time_tight;

    // Try multiple strategies, pick best by eval function
    EvalMetrics best_eval;
    int first=1;
    int any_jm_le_r=0;

    #define TRY_STRATEGY() do { \
        EvalMetrics cur_eval=collect_metrics(m); \
        if(cur_eval.jm<=g_r) any_jm_le_r=1; \
        if(first||better_metrics(cur_eval,best_eval)){ \
            best_eval=cur_eval; first=0; \
            memcpy(sv_out, out_load, g_l*sizeof(out_load[0])); \
            memcpy(sv_in, in_load, g_l*sizeof(in_load[0])); \
            memcpy(sv_port, fl_port, fl_count*sizeof(short)); \
        } \
    } while(0)

    // S1: standard (local*2, global*1, no hardcap) + swap
    run_greedy(m, 2, 1, 0);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // S2: hardcap (local*2, global*1, hardcap=1) + swap
    run_greedy(m, 2, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // S3: reversed order + hardcap + swap
    run_greedy(m, 2, 1, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    if(time_tight) goto portfolio_done;

    // S4: hardcap, no swap
    run_greedy(m, 2, 1, 1);
    TRY_STRATEGY();

    // S5: reversed order, no hardcap + swap
    run_greedy(m, 2, 1, 0, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // S6: stronger global (local*3, global*2, hardcap) + swap
    run_greedy(m, 3, 2, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // S6b: FTRL greedy (quadratic global penalty) + swap
    run_greedy_ftrl(m, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // S6c: FTRL reversed + swap
    run_greedy_ftrl(m, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // S6d: FTRL strong penalty (sc_div=4) + swap
    run_greedy_ftrl(m, 1, 0, 4);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // S6e: FTRL weak penalty (sc_div=1) + swap
    run_greedy_ftrl(m, 1, 0, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    // Local-dominant FTRL: keep the quadratic global regularization, but make
    // jm reduction more competitive on overflow-heavy jobs.
    if(g_p<=16){
        run_greedy_ftrl(m, 1, 0, 2, 6);
        run_swap(m);
        TRY_STRATEGY();

        run_greedy_ftrl(m, 1, 1, 2, 6);
        run_swap(m);
        TRY_STRATEGY();
    }

    // S6e2-S6e5: local-first hardcap candidates. These preserve the same
    // structural jm on some proxy cases while sometimes lowering conflicts.
    run_greedy(m, 1000, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    run_greedy(m, 1000, 1, 1, 1);
    run_swap(m);
    run_jm_repair(m);
    TRY_STRATEGY();

    run_greedy(m, 1000, 1, 1);
    TRY_STRATEGY();

    run_greedy(m, 1000, 1, 1, 1);
    TRY_STRATEGY();

    if(!huge_job){
        // S6f-S6g: FTRL random restarts (shuffled orders with quadratic penalty)
        for(int i=0;i<fl_count;++i) fl_order[i]=i;
        run_greedy_ftrl(m, 1, 2, 2);
        run_swap(m);
        TRY_STRATEGY();
        for(int i=0;i<fl_count;++i) fl_order[i]=i;
        run_greedy_ftrl(m, 1, 3, 2);
        run_swap(m);
        TRY_STRATEGY();

        // S6h: Exponential potential (eta=3, cubic penalty) + swap
        run_greedy_exp(m, 1, 0, 3);
        run_swap(m);
        TRY_STRATEGY();

        // S6i: Adaptive FTRL (early=conservative, late=aggressive) + swap
        run_greedy_ftrl_adaptive(m, 1);
        run_swap(m);
        TRY_STRATEGY();

        // S6j: Adaptive FTRL reversed + swap
        run_greedy_ftrl_adaptive(m, 1, 1);
        run_swap(m);
        TRY_STRATEGY();

        // S7-S10: random restart with hardcap + swap (4 different seeds)
        for(int seed=2;seed<=5;++seed){
            for(int i=0;i<fl_count;++i) fl_order[i]=i;
            run_greedy(m, 2, 1, 1, seed);
            run_swap(m);
            run_jm_repair(m);
            TRY_STRATEGY();
        }

        // Extra random restarts for tight cases (Maxsingler still > r)
        // Only when job is small enough and violation is marginal (jm == r+1)
        if(!any_jm_le_r && best_eval.jm==g_r+1 && fl_count<=2000){
            for(int seed=6;seed<=25;++seed){
                for(int i=0;i<fl_count;++i) fl_order[i]=i;
                run_greedy(m, 2, 1, 1, seed);
                run_swap(m);
                run_jm_repair(m);
                TRY_STRATEGY();
                if(any_jm_le_r) break;
            }
        }
    }

    // Only run expensive global strategies when some candidate already solves
    // the per-job overflow. When jm still exceeds r, these global refinements
    // add a lot of runtime on huge jobs and rarely change the outcome.
    if(any_jm_le_r){

    // S11: global-dominant (local*1, global*3, hardcap) + swap + global swap + lns
    run_greedy(m, 1, 3, 1);
    run_swap(m);
    run_global_swap(m);
    run_lns(m);
    TRY_STRATEGY();

    // S12: global-dominant reversed (local*1, global*3, hardcap, reversed) + swap + global swap + lns
    run_greedy(m, 1, 3, 1, 1);
    run_swap(m);
    run_global_swap(m);
    run_lns(m);
    TRY_STRATEGY();

    // S13: extreme global (local*1, global*5, hardcap) + swap + global swap + lns
    run_greedy(m, 1, 5, 1);
    run_swap(m);
    run_global_swap(m);
    run_lns(m);
    TRY_STRATEGY();

    // S14: future-gmax greedy (hardcap) + swap + global swap + lns
    run_greedy_fgmax(m, 1);
    run_swap(m);
    run_global_swap(m);
    run_lns(m);
    TRY_STRATEGY();

    // S15: future-gmax greedy reversed (hardcap) + swap + global swap + lns
    run_greedy_fgmax(m, 1, 1);
    run_swap(m);
    run_global_swap(m);
    run_lns(m);
    TRY_STRATEGY();

    // S16: FTRL (sc_div=2) + global swap + lns
    run_greedy_ftrl(m, 1, 0, 2);
    run_swap(m);
    run_global_swap(m);
    run_lns(m);
    TRY_STRATEGY();

    // S17: FTRL strong (sc_div=4) + global swap + lns
    run_greedy_ftrl(m, 1, 0, 4);
    run_swap(m);
    run_global_swap(m);
    run_lns(m);
    TRY_STRATEGY();

    // S18: FTRL reversed (sc_div=2) + global swap + lns
    run_greedy_ftrl(m, 1, 1, 2);
    run_swap(m);
    run_global_swap(m);
    run_lns(m);
    TRY_STRATEGY();

    } // end if any_jm_le_r

    portfolio_done:
    // Restore best strategy
    memcpy(out_load, sv_out, g_l*sizeof(out_load[0]));
    memcpy(in_load, sv_in, g_l*sizeof(in_load[0]));
    memcpy(fl_port, sv_port, fl_count*sizeof(short));

    // Final global refinement is worthwhile on balanced jobs, but skip it on
    // very large overflowed jobs where it mainly burns time.
    int restored_jm=get_job_max(m);
    if(!time_tight && (restored_jm<=g_r || job_work<=120000)) run_global_swap(m);

    // Min-conflicts repair for Maxsingler violations
    if(fl_count<=6000&&get_job_max(m)>g_r) run_mc_repair(m);

    // If `jm` still exceeds a simple lower bound, try exact single-flow moves
    // out of the hottest `jm=r+1` cells before broader rebuild operators.
    run_lowr_hotcell_exact(m);

    // Rebuild around the most overloaded leaf-port-phase cells first. This is
    // meant to target `jm/fg` gap cases more directly than the source-card
    // rebuild that mainly improves conflict terms.
    run_lowr_cell_core_rebuild(m);

    // When `fg` still exceeds a simple lower bound, rebuild the flows attached
    // to the hottest leaf-side directly. This is the dedicated `fg-gap` branch.
    run_lowr_hotleaf_rebuild(m);

    // Rebuild the highest-pressure overflow source cards as a small local
    // subproblem. This is the first low-r operator that coordinates multiple
    // flows together instead of only patching one flow at a time.
    run_lowr_card_core_rebuild(m);

    // Low-r perturb-restart repair: keep the `r=2` path restricted to wider
    // `p>=32` jobs, while `r=3` can still use it at `p>=16`. This keeps the
    // search focused on structures that have shown non-negative transfer.
    int lowr_jm=get_job_max(m);
    int enable_lowr_repair=((g_r==2&&g_p>=32)||(g_r==3&&g_p>=16));
    if(enable_lowr_repair&&fl_count<=4500&&job_work<=70000&&lowr_jm==g_r+1)
        run_random_start_repair(m);

    int allow_extra_pc_chain=1;
    if(job_work>100000) allow_extra_pc_chain=0;
    else if(job_work>80000&&!(g_p>=16&&m>=17&&fl_count<=5500)) allow_extra_pc_chain=0;
    if(job_work>50000&&fl_count>5000) allow_extra_pc_chain=0;
    if(g_time_tight) allow_extra_pc_chain=0;

    run_port_consistency(m);
    run_port_consistency_perport_refine(m);
    run_port_consistency(m);
    if(allow_extra_pc_chain){
        run_port_consistency_perport_refine(m);
        run_port_consistency(m);
        run_port_consistency_perport_refine(m);
        run_port_consistency(m);
    }
    if(!g_time_tight){
        run_relaxed_swap(m);
        run_neutral_swap(m);
        run_relaxed_swap(m);
    }
    run_cross_dest_swap(m);
    if(!g_time_tight){
        run_neutral_swap(m);
        run_relaxed_swap(m);
    }

    // Low-r make-room consistency: for cards with high Cbtphsc on low-r jobs,
    // move blocker flows off the dominant port to make room for consistency moves
    EvalMetrics mr_gate_base=collect_metrics(m);
    int enable_r4_makeroom=(g_r==4&&g_p>=16&&fl_count<=4500&&job_work<=40000&&!g_time_tight&&mr_gate_base.fg>=32);
    int enable_makeroom=((g_r<=3&&g_p>=16&&fl_count<=6000)||enable_r4_makeroom);
    if(enable_makeroom){
        // Backup state for rollback if MM worsens
        memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
        memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
        memcpy(bk_port, fl_port, fl_count*sizeof(short));
        EvalMetrics mr_base=mr_gate_base;

        // Rebuild cpm/cppc fresh
        memset(cpm,0,sizeof(cpm));memset(cppc,0,sizeof(cppc));
        for(int i=0;i<fl_count;++i){
            if(fl_sl[i]==fl_dl[i]||fl_port[i]<0) continue;
            int c=fl_src[i],p=fl_port[i];
            unsigned int mk=fl_pmask[i];
            while(mk){int ph=__builtin_ctz(mk);cppc[c][ph][p]++;cpm[c][ph]|=(1u<<p);mk&=mk-1;}
        }
        int total_cbt_before=0;
        for(int c=0;c<12800;++c) total_cbt_before+=card_cbtphsc(c,m);
        if(total_cbt_before>0){
            for(int mr_iter=0;mr_iter<3;++mr_iter){
                int mr_improved=0;
                for(int fi=0;fi<fl_count;++fi){
                    int sl=fl_sl[fi],dl=fl_dl[fi],cp=fl_port[fi],ci=fl_src[fi];
                    if(sl==dl||cp<0) continue;
                    if(card_cbtphsc(ci,m)==0) continue;
                    // Try the top-2 candidate ports for this card instead of
                    // only the single dominant port.
                    int dp_cnt[32]={};
                    for(int ph=0;ph<m;++ph)
                        if(cpm[ci][ph]) for(int pk=0;pk<g_p;++pk) if(cppc[ci][ph][pk]) dp_cnt[pk]+=cppc[ci][ph][pk];
                    unsigned int mask=fl_pmask[fi];
                    int target_ports[2]={-1,-1};
                    int target_scores[2]={-1,-1};
                    for(int pk=0;pk<g_p;++pk){
                        int score=dp_cnt[pk];
                        if(score<=0||pk==cp) continue;
                        if(score>target_scores[0]){
                            target_scores[1]=target_scores[0];
                            target_ports[1]=target_ports[0];
                            target_scores[0]=score;
                            target_ports[0]=pk;
                        } else if(score>target_scores[1]){
                            target_scores[1]=score;
                            target_ports[1]=pk;
                        }
                    }
                    int best_net=-1,best_bfi=-1,best_bap=-1,best_dp=-1;
                    for(int dpk=0;dpk<2;++dpk){
                        int dp=target_ports[dpk];
                        if(dp<0) continue;
                        unsigned int blocked=0;
                        unsigned int mk=mask;
                        while(mk){
                            int ph=__builtin_ctz(mk);
                            if(out_load[sl][dp][ph]>=g_r||in_load[dl][dp][ph]>=g_r)
                                blocked|=(1u<<ph);
                            mk&=mk-1;
                        }
                        if(!blocked){
                            int before_cbt=card_cbtphsc(ci,m);
                            unsigned int m3=mask;
                            while(m3){int ph=__builtin_ctz(m3);
                                cppc[ci][ph][cp]--;if(!cppc[ci][ph][cp])cpm[ci][ph]&=~(1u<<cp);
                                cppc[ci][ph][dp]++;cpm[ci][ph]|=(1u<<dp);m3&=m3-1;}
                            int after_cbt=card_cbtphsc(ci,m);
                            int net=before_cbt-after_cbt;
                            m3=mask;while(m3){int ph=__builtin_ctz(m3);
                                cppc[ci][ph][dp]--;if(!cppc[ci][ph][dp])cpm[ci][ph]&=~(1u<<dp);
                                cppc[ci][ph][cp]++;cpm[ci][ph]|=(1u<<cp);m3&=m3-1;}
                            if(net>best_net){best_net=net;best_bfi=-1;best_bap=-1;best_dp=dp;}
                            continue;
                        }
                        // Try to find a single blocker flow on dp that covers
                        // at least one blocked phase.
                        for(int bfi=0;bfi<fl_count;++bfi){
                            if(bfi==fi) continue;
                            int bsl=fl_sl[bfi],bdl=fl_dl[bfi],bcp=fl_port[bfi];
                            if(bsl==bdl||bcp<0) continue;
                            int on_dp_sl=(bsl==sl&&bcp==dp);
                            int on_dp_dl=(bdl==dl&&bcp==dp);
                            if(!on_dp_sl&&!on_dp_dl) continue;
                            unsigned int bmask=fl_pmask[bfi];
                            if(!(bmask&blocked)) continue;
                            for(int ap=0;ap<g_p;++ap){
                                if(ap==dp) continue;
                                int bok=1;
                                unsigned int m2=bmask;
                                while(m2){
                                    int ph=__builtin_ctz(m2);
                                    if(out_load[bsl][ap][ph]>=g_r){bok=0;break;}
                                    if(in_load[bdl][ap][ph]>=g_r){bok=0;break;}
                                    m2&=m2-1;
                                }
                                if(!bok) continue;
                                unsigned int new_blocked=0;
                                mk=mask;
                                while(mk){
                                    int ph=__builtin_ctz(mk);
                                    int out_dp=out_load[sl][dp][ph]-((on_dp_sl&&(bmask&(1u<<ph)))?1:0);
                                    int in_dp=in_load[dl][dp][ph]-((on_dp_dl&&(bmask&(1u<<ph)))?1:0);
                                    if(out_dp>=g_r||in_dp>=g_r) new_blocked|=(1u<<ph);
                                    mk&=mk-1;
                                }
                                if(new_blocked) continue;
                                int bci=fl_src[bfi];
                                int before_cbt=card_cbtphsc(ci,m)+card_cbtphsc(bci,m);
                                unsigned int m3;
                                m3=bmask;while(m3){int ph=__builtin_ctz(m3);
                                    cppc[bci][ph][dp]--;if(!cppc[bci][ph][dp])cpm[bci][ph]&=~(1u<<dp);
                                    cppc[bci][ph][ap]++;cpm[bci][ph]|=(1u<<ap);m3&=m3-1;}
                                m3=mask;while(m3){int ph=__builtin_ctz(m3);
                                    cppc[ci][ph][cp]--;if(!cppc[ci][ph][cp])cpm[ci][ph]&=~(1u<<cp);
                                    cppc[ci][ph][dp]++;cpm[ci][ph]|=(1u<<dp);m3&=m3-1;}
                                int after_cbt=card_cbtphsc(ci,m)+card_cbtphsc(bci,m);
                                int net=before_cbt-after_cbt;
                                m3=mask;while(m3){int ph=__builtin_ctz(m3);
                                    cppc[ci][ph][dp]--;if(!cppc[ci][ph][dp])cpm[ci][ph]&=~(1u<<dp);
                                    cppc[ci][ph][cp]++;cpm[ci][ph]|=(1u<<cp);m3&=m3-1;}
                                m3=bmask;while(m3){int ph=__builtin_ctz(m3);
                                    cppc[bci][ph][ap]--;if(!cppc[bci][ph][ap])cpm[bci][ph]&=~(1u<<ap);
                                    cppc[bci][ph][dp]++;cpm[bci][ph]|=(1u<<dp);m3&=m3-1;}
                                if(net>best_net){best_net=net;best_bfi=bfi;best_bap=ap;best_dp=dp;}
                            }
                        }
                    }
                    if(best_dp<0||best_net<=0) continue;
                    if(best_bfi<0){
                        unsigned int m3=mask;
                        while(m3){int ph=__builtin_ctz(m3);
                            out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;
                            out_load[sl][best_dp][ph]++;in_load[dl][best_dp][ph]++;
                            cppc[ci][ph][cp]--;if(!cppc[ci][ph][cp])cpm[ci][ph]&=~(1u<<cp);
                            cppc[ci][ph][best_dp]++;cpm[ci][ph]|=(1u<<best_dp);m3&=m3-1;}
                        fl_port[fi]=(short)best_dp;
                        mr_improved++;
                        continue;
                    }
                    // Commit blocker move, then move fi to the selected target port.
                    int bci=fl_src[best_bfi];
                    unsigned int bmask=fl_pmask[best_bfi];
                    int bsl=fl_sl[best_bfi],bdl=fl_dl[best_bfi];
                    unsigned int m3=bmask;while(m3){int ph=__builtin_ctz(m3);
                        out_load[bsl][best_dp][ph]--;in_load[bdl][best_dp][ph]--;
                        out_load[bsl][best_bap][ph]++;in_load[bdl][best_bap][ph]++;
                        cppc[bci][ph][best_dp]--;if(!cppc[bci][ph][best_dp])cpm[bci][ph]&=~(1u<<best_dp);
                        cppc[bci][ph][best_bap]++;cpm[bci][ph]|=(1u<<best_bap);m3&=m3-1;}
                    fl_port[best_bfi]=(short)best_bap;
                    m3=mask;while(m3){int ph=__builtin_ctz(m3);
                        out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;
                        out_load[sl][best_dp][ph]++;in_load[dl][best_dp][ph]++;
                        cppc[ci][ph][cp]--;if(!cppc[ci][ph][cp])cpm[ci][ph]&=~(1u<<cp);
                        cppc[ci][ph][best_dp]++;cpm[ci][ph]|=(1u<<best_dp);m3&=m3-1;}
                    fl_port[fi]=(short)best_dp;
                    mr_improved++;
                }
                if(!mr_improved) break;
            }
        }
        // Post-check: revert if Maxmultir (fg) worsened
        EvalMetrics mr_after=collect_metrics(m);
        if(mr_after.fg>mr_base.fg||(mr_after.fg==mr_base.fg&&mr_after.jm>mr_base.jm)){
            memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
            memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
            memcpy(fl_port, bk_port, fl_count*sizeof(short));
        } else if(enable_r4_makeroom){
            memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
            memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
            memcpy(bk_port, fl_port, fl_count*sizeof(short));
            EvalMetrics follow_base=collect_metrics(m);
            run_port_consistency(m);
            run_neutral_swap(m);
            run_relaxed_swap(m);
            EvalMetrics follow_after=collect_metrics(m);
            if(!better_metrics(follow_after,follow_base)){
                memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
                memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
                memcpy(fl_port, bk_port, fl_count*sizeof(short));
            }
        }
    }

    // Cbttskc reduction pass: move flows from high-cumulative ports to lower ones
    // Use conservative global state: save pre-pass max_phase for global update
    static short pre_ct_mo[MAX_LEAFS][MAX_PORTS];
    static short pre_ct_mi[MAX_LEAFS][MAX_PORTS];
    int ct_pass_ran=0;
    if(!g_time_tight){
        for(int leaf=0;leaf<g_l;++leaf)
            for(int pk=0;pk<g_p;++pk){
                short mo=0,mi=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                    if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
                }
                pre_ct_mo[leaf][pk]=mo;pre_ct_mi[leaf][pk]=mi;
            }
        memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
        memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
        memcpy(bk_port, fl_port, fl_count*sizeof(short));
        EvalMetrics ct_base=collect_metrics(m);
        run_cbttskc_reduce(m);
        EvalMetrics ct_after=collect_metrics(m);
        if(ct_after.fg>ct_base.fg||(ct_after.fg==ct_base.fg&&ct_after.jm>ct_base.jm)){
            memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
            memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
            memcpy(fl_port, bk_port, fl_count*sizeof(short));
        } else {
            ct_pass_ran=1;
            run_port_consistency(m);
            run_neutral_swap(m);
            run_relaxed_swap(m);
            run_cross_dest_swap(m);
        }
    }

    // SA composite pass: escape local optima with unified objective
    if(!g_time_tight){
        memcpy(bk_out, out_load, g_l*sizeof(out_load[0]));
        memcpy(bk_in, in_load, g_l*sizeof(in_load[0]));
        memcpy(bk_port, fl_port, fl_count*sizeof(short));
        EvalMetrics sa_base=collect_metrics(m);
        run_sa_composite(m);
        EvalMetrics sa_after=collect_metrics(m);
        if(sa_after.fg>sa_base.fg||(sa_after.fg==sa_base.fg&&sa_after.jm>sa_base.jm)){
            memcpy(out_load, bk_out, g_l*sizeof(out_load[0]));
            memcpy(in_load, bk_in, g_l*sizeof(in_load[0]));
            memcpy(fl_port, bk_port, fl_count*sizeof(short));
        } else {
            // Post-SA CB recovery: SA may have moved flows enabling new CB improvements
            run_neutral_swap(m);
            run_relaxed_swap(m);
        }
    }

    // Update g_hist_max_jm with this job's final jm
    int final_jm = get_job_max(m);
    if(final_jm > g_hist_max_jm) g_hist_max_jm = final_jm;

    // Update global state - use pre-pass max_phase if Cbttskc pass ran
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            if(ct_pass_ran){
                global_out[leaf][pk]+=pre_ct_mo[leaf][pk];
                global_in[leaf][pk]+=pre_ct_mi[leaf][pk];
            } else {
                int mo=0,mi=0;
                for(int ph=0;ph<m;++ph){if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];}
                global_out[leaf][pk]+=mo;global_in[leaf][pk]+=mi;
            }
        }
    fast_write(fl_count);write_char('\n');flush_out();fflush(stdout);
    for(int i=0;i<fl_count;++i){fast_write(fl_src[i]);write_char(' ');fast_write(fl_dst[i]);write_char(' ');fast_write(fl_port[i]);if(i!=fl_count-1)write_char(' ');}
    write_char('\n');flush_out();fflush(stdout);
}

int main(){
    g_start_clock=clock();
    memset(ht_key,-1,sizeof(ht_key));
    int n=fast_read_int();
    g_n=n; g_job_idx=0; g_hist_max_jm=0;
    g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    for(int i=0;i<n;++i){g_job_idx=i;solve_job();}
    return 0;
}
