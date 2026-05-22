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
static int ht_key[HT_SIZE],ht_val[HT_SIZE],ht_used[MAX_FLOWS];
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
// Global: use SUM of all phase loads (not just max) for richer info
static int global_out[MAX_LEAFS][MAX_PORTS];
static int global_in[MAX_LEAFS][MAX_PORTS];
static int g_l,g_p,g_r,g_pr,g_n;

inline int greedy_cost(int sl, int dl, int pk, unsigned int mask){
    int cost=0;
    unsigned int m2=mask;
    while(m2){
        int ph=__builtin_ctz(m2);
        int o=out_load[sl][pk][ph]+1;
        int iv=in_load[dl][pk][ph]+1;
        int v=o>iv?o:iv;if(v>cost)cost=v;
        m2&=m2-1;
    }
    return cost*4+global_out[sl][pk]+global_in[dl][pk];
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

    // Pass 1: greedy
    for(int i=0;i<fl_count;++i){
        int sl=fl_src[i]/g_pr,dl=fl_dst[i]/g_pr;
        if(sl==dl){fl_port[i]=-1;continue;}
        unsigned int mask=fl_pmask[i];
        int bp=0,bc=0x7fffffff;
        for(int pk=0;pk<g_p;++pk){
            int c=greedy_cost(sl,dl,pk,mask);
            if(c<bc){bc=c;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }

    // Pass 2: re-greedy (reverse order)
    for(int i=fl_count-1;i>=0;--i){
        int sl=fl_src[i]/g_pr,dl=fl_dst[i]/g_pr;
        if(sl==dl) continue;
        int old_p=fl_port[i];
        unsigned int mask=fl_pmask[i];
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][old_p][ph]--;in_load[dl][old_p][ph]--;m2&=m2-1;}
        int bp=0,bc=0x7fffffff;
        for(int pk=0;pk<g_p;++pk){
            int c=greedy_cost(sl,dl,pk,mask);
            if(c<bc){bc=c;bp=pk;}
        }
        fl_port[i]=(short)bp;
        m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }

    // Update global with SUM of phase loads (not max)
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int so=0,si=0;
            for(int ph=0;ph<m;++ph){so+=out_load[leaf][pk][ph];si+=in_load[leaf][pk][ph];}
            global_out[leaf][pk]+=so;global_in[leaf][pk]+=si;
        }

    fast_write(fl_count);write_char('\n');flush_out();fflush(stdout);
    for(int i=0;i<fl_count;++i){fast_write(fl_src[i]);write_char(' ');fast_write(fl_dst[i]);write_char(' ');fast_write(fl_port[i]);if(i!=fl_count-1)write_char(' ');}
    write_char('\n');flush_out();fflush(stdout);
}

int main(){
    memset(ht_key,-1,sizeof(ht_key));
    g_n=fast_read_int();
    g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    for(int i=0;i<g_n;++i)solve_job();
    return 0;
}
