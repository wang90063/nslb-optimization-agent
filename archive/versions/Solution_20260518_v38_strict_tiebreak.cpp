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
static int fl_sl[MAX_FLOWS],fl_dl[MAX_FLOWS];
static short card_pref[MAX_CARDS]; // preferred port per source card (-1=none)
static short bk_out_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short bk_in_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
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
    memset(out_load,0,g_l*sizeof(out_load[0]));
    memset(in_load,0,g_l*sizeof(in_load[0]));
    memset(card_pref,-1,g_pr*sizeof(short));
    for(int i=0;i<fl_count;++i){
        fl_sl[i]=fl_src[i]/g_pr;
        fl_dl[i]=fl_dst[i]/g_pr;
    }

    // Pass 1: greedy with STRICT tiebreaker for card port consistency
    // Only prefer card's port when cost is EXACTLY equal to best
    for(int i=0;i<fl_count;++i){
        int sl=fl_sl[i],dl=fl_dl[i];
        if(sl==dl){fl_port[i]=-1;continue;}
        unsigned int mask=fl_pmask[i];
        int src_card=fl_src[i];
        int pref=card_pref[src_card];
        int bp=0,bc=0x7fffffff;
        int pref_cost=0x7fffffff;
        for(int pk=0;pk<g_p;++pk){
            int cost=0;
            unsigned int m2=mask;
            while(m2){
                int ph=__builtin_ctz(m2);
                int o=out_load[sl][pk][ph]+1;
                int iv=in_load[dl][pk][ph]+1;
                int v=o>iv?o:iv;if(v>cost)cost=v;
                m2&=m2-1;
            }
            int go=global_out[sl][pk],gi=global_in[dl][pk];
            int gv=go>gi?go:gi;
            int total=cost*2+gv;
            if(total<bc){bc=total;bp=pk;}
            if(pk==pref) pref_cost=total;
        }
        // Strict tiebreaker: use preferred port only if its cost equals the best
        if(pref>=0 && pref_cost==bc) bp=pref;
        fl_port[i]=(short)bp;
        if(card_pref[src_card]<0) card_pref[src_card]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }

    // Pass 2: all-or-nothing safe swap
    int pre_swap_max = get_job_max(m);
    if(pre_swap_max > g_r){
        memcpy(bk_out_load, out_load, g_l*sizeof(out_load[0]));
        memcpy(bk_in_load, in_load, g_l*sizeof(in_load[0]));
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
                int on_bottleneck=0;
                unsigned int m2=mask;
                while(m2){
                    int ph=__builtin_ctz(m2);
                    if(out_load[sl][cp][ph]==mx||in_load[dl][cp][ph]==mx){on_bottleneck=1;break;}
                    m2&=m2-1;
                }
                if(!on_bottleneck) continue;
                int best_new=-1,best_new_max=mx;
                for(int pk=0;pk<g_p;++pk){
                    if(pk==cp) continue;
                    int new_max=0;
                    m2=mask;
                    while(m2){
                        int ph=__builtin_ctz(m2);
                        int no=out_load[sl][pk][ph]+1;if(no>new_max)new_max=no;
                        int ni=in_load[dl][pk][ph]+1;if(ni>new_max)new_max=ni;
                        int oo=out_load[sl][cp][ph]-1;if(oo>new_max)new_max=oo;
                        int oi=in_load[dl][cp][ph]-1;if(oi>new_max)new_max=oi;
                        m2&=m2-1;
                    }
                    if(new_max<best_new_max){best_new_max=new_max;best_new=pk;}
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
        int post_swap_max = get_job_max(m);
        if(post_swap_max >= pre_swap_max){
            memcpy(out_load, bk_out_load, g_l*sizeof(out_load[0]));
            memcpy(in_load, bk_in_load, g_l*sizeof(in_load[0]));
            memcpy(fl_port, bk_port, fl_count*sizeof(short));
        }
    }

    // update global
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
    g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    for(int i=0;i<n;++i)solve_job();
    return 0;
}
