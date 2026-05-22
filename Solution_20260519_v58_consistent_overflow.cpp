#include <stdio.h>
#include <string.h>
#include <stdlib.h>
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
static int g_hist_max_jm; // 历史最大 jm，用于判断当前 job 是否是 Maxsingler 瓶颈
static int g_fixed_overflow_mode; // testcase级别固定overflow策略，降低级联
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

void run_swap(int m);

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
        for(int pk=0;pk<g_p;++pk){
            int cost=0;
            int exceeds=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                int v=o>iv?o:iv;if(v>cost)cost=v;
                if(hardcap&&(o>g_r||iv>g_r)) exceeds=1;
                m2&=m2-1;
            }
            int go=global_out[sl][pk],gi=global_in[dl][pk];
            int gv=go>gi?go:gi;
            cost=cost*local_w+gv*global_w;
            if(exceeds) cost+=10000;
            if(cost<bc){bc=cost;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
}

// FTRL-inspired greedy: quadratic penalty on global load
// sc_div controls penalty strength: smaller = stronger quadratic
void run_greedy_ftrl(int m, int hardcap, int rev=0, int sc_div=2){
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
            int cost=local_max*2 + gv + gv*gv/scale;
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

void run_overflow_mode(int m, int mode){
    switch(mode){
        case 0:
            run_greedy(m, 2, 1, 1);
            run_swap(m);
            break;
        case 1:
            run_greedy(m, 2, 1, 1, 1);
            run_swap(m);
            break;
        case 2:
            run_greedy_ftrl(m, 1);
            run_swap(m);
            break;
        case 3:
            run_greedy_ftrl(m, 1, 0, 4);
            run_swap(m);
            break;
        default:
            run_greedy_ftrl(m, 1);
            run_swap(m);
            break;
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
// Strict constraint: never increase max_phase_load on any (leaf,port)
static int pc_flows[MAX_FLOWS];
static int pc_mark[MAX_FLOWS];
void run_port_consistency(int m){
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
        int best_p=0;
        for(int pk=1;pk<g_p;++pk)
            if(port_count[pk]>port_count[best_p]) best_p=pk;
        for(int k=0;k<cnt;++k){
            int fi=pc_flows[k];
            int cp=fl_port[fi];
            if(cp==best_p) continue;
            int sl=fl_sl[fi],dl=fl_dl[fi];
            unsigned int mask=fl_pmask[fi];
            int cur_max_out=0,cur_max_in=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[sl][best_p][ph]>cur_max_out)cur_max_out=out_load[sl][best_p][ph];
                if(in_load[dl][best_p][ph]>cur_max_in)cur_max_in=in_load[dl][best_p][ph];
            }
            unsigned int m2=mask; int ok=1;
            while(m2){
                int ph=__builtin_ctz(m2);
                if(out_load[sl][best_p][ph]+1>cur_max_out||in_load[dl][best_p][ph]+1>cur_max_in){ok=0;break;}
                m2&=m2-1;
            }
            if(!ok) continue;
            m2=mask;
            while(m2){int ph=__builtin_ctz(m2);out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;out_load[sl][best_p][ph]++;in_load[dl][best_p][ph]++;m2&=m2-1;}
            fl_port[fi]=(short)best_p;
        }
    }
}

inline long long eval_strategy(int m){
    int jm=get_job_max(m);
    int fg=get_future_gmax(m);
    int ci=get_cinphsc(m);
    if(jm <= g_r){
        return (long long)fg*10000 + (long long)jm*100 + (long long)ci;
    }
    if(jm <= g_hist_max_jm){
        return (long long)fg*10000 + (long long)jm*100 + (long long)ci;
    }
    return (long long)100000000 + (long long)jm*10000 + (long long)fg*1000 + (long long)ci;
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

    // Try multiple strategies, pick best by eval function
    long long best_score=0x7fffffffffffffffLL;
    int first=1;
    int any_jm_le_r=0;
    int candidate_mode=-1;
    int best_mode=-1;
    int locked_overflow_only=0;

    #define TRY_STRATEGY() do { \
        int cur_jm=get_job_max(m); \
        if(cur_jm<=g_r) any_jm_le_r=1; \
        long long sc=eval_strategy(m); \
        if(first||sc<best_score){ \
            best_score=sc; first=0; \
            best_mode=candidate_mode; \
            memcpy(sv_out, out_load, g_l*sizeof(out_load[0])); \
            memcpy(sv_in, in_load, g_l*sizeof(in_load[0])); \
            memcpy(sv_port, fl_port, fl_count*sizeof(short)); \
        } \
    } while(0)

    if(g_fixed_overflow_mode>=0){
        run_overflow_mode(m, g_fixed_overflow_mode);
        if(get_job_max(m)>g_r){
            locked_overflow_only=1;
            best_score=eval_strategy(m);
            first=0;
            best_mode=g_fixed_overflow_mode;
            memcpy(sv_out, out_load, g_l*sizeof(out_load[0]));
            memcpy(sv_in, in_load, g_l*sizeof(in_load[0]));
            memcpy(sv_port, fl_port, fl_count*sizeof(short));
        }
    }

    if(!locked_overflow_only){
    // S1: standard (local*2, global*1, no hardcap) + swap
    candidate_mode=-1;
    run_greedy(m, 2, 1, 0);
    run_swap(m);
    TRY_STRATEGY();

    // S2: hardcap (local*2, global*1, hardcap=1) + swap
    candidate_mode=0;
    run_greedy(m, 2, 1, 1);
    run_swap(m);
    TRY_STRATEGY();

    // S3: reversed order + hardcap + swap
    candidate_mode=1;
    run_greedy(m, 2, 1, 1, 1);
    run_swap(m);
    TRY_STRATEGY();

    // S4: hardcap, no swap
    candidate_mode=-1;
    run_greedy(m, 2, 1, 1);
    TRY_STRATEGY();

    // S5: reversed order, no hardcap + swap
    candidate_mode=-1;
    run_greedy(m, 2, 1, 0, 1);
    run_swap(m);
    TRY_STRATEGY();

    // S6: stronger global (local*3, global*2, hardcap) + swap
    candidate_mode=-1;
    run_greedy(m, 3, 2, 1);
    run_swap(m);
    TRY_STRATEGY();

    // S6b: FTRL greedy (quadratic global penalty) + swap
    candidate_mode=2;
    run_greedy_ftrl(m, 1);
    run_swap(m);
    TRY_STRATEGY();

    // S6c: FTRL reversed + swap
    candidate_mode=-1;
    run_greedy_ftrl(m, 1, 1);
    run_swap(m);
    TRY_STRATEGY();

    // S6d: FTRL strong penalty (sc_div=4) + swap
    candidate_mode=3;
    run_greedy_ftrl(m, 1, 0, 4);
    run_swap(m);
    TRY_STRATEGY();

    // S6e: FTRL weak penalty (sc_div=1) + swap
    candidate_mode=-1;
    run_greedy_ftrl(m, 1, 0, 1);
    run_swap(m);
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
            TRY_STRATEGY();
        }
    }

    if(!any_jm_le_r && g_fixed_overflow_mode<0 && g_job_idx*2<g_n){
        if(best_mode>=0) g_fixed_overflow_mode=best_mode;
        else g_fixed_overflow_mode=2;
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
    } // end if !locked_overflow_only

    // Restore best strategy
    memcpy(out_load, sv_out, g_l*sizeof(out_load[0]));
    memcpy(in_load, sv_in, g_l*sizeof(in_load[0]));
    memcpy(fl_port, sv_port, fl_count*sizeof(short));

    // Final global refinement is worthwhile on balanced jobs, but skip it on
    // very large overflowed jobs where it mainly burns time.
    int restored_jm=get_job_max(m);
    if(restored_jm<=g_r || job_work<=120000) run_global_swap(m);

    // Only consolidate same-card flows when there is no phase overflow.
    // On overflowed jobs this post-pass often trades Cbtphsc for a much larger
    // Cinphsc increase, especially on AI-style heavy collective patterns.
    if(get_cinphsc(m)==0) run_port_consistency(m);

    // Update g_hist_max_jm with this job's final jm
    int final_jm = get_job_max(m);
    if(final_jm > g_hist_max_jm) g_hist_max_jm = final_jm;

    // Update global state
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int mo=0,mi=0;
            for(int ph=0;ph<m;++ph){if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];}
            global_out[leaf][pk]+=mo;global_in[leaf][pk]+=mi;
        }
    fast_write(fl_count);write_char('\n');flush_out();fflush(stdout);
    for(int i=0;i<fl_count;++i){fast_write(fl_src[i]);write_char(' ');fast_write(fl_dst[i]);write_char(' ');fast_write(fl_port[i]);if(i!=fl_count-1)write_char(' ');}
    write_char('\n');flush_out();fflush(stdout);
}

int main(){
    memset(ht_key,-1,sizeof(ht_key));
    int n=fast_read_int();
    g_n=n; g_job_idx=0; g_hist_max_jm=0; g_fixed_overflow_mode=-1;
    g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    for(int i=0;i<n;++i){g_job_idx=i;solve_job();}
    return 0;
}
