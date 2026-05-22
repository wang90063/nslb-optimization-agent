#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define FAST_GET_CHAR getchar_unlocked
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
inline int fast_read_int(){int c=FAST_GET_CHAR();while(c<'0'||c>'9')c=FAST_GET_CHAR();int x=0;while(c>='0'&&c<='9'){x=x*10+(c-'0');c=FAST_GET_CHAR();}return x;}
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

void solve_job(int job_idx){
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
    for(int i=0;i<fl_count;++i){
        fl_sl[i]=fl_src[i]/g_pr;
        fl_dl[i]=fl_dst[i]/g_pr;
    }
    // Greedy (same as v33)
    for(int i=0;i<fl_count;++i){
        int sl=fl_sl[i],dl=fl_dl[i];
        if(sl==dl){fl_port[i]=-1;continue;}
        unsigned int mask=fl_pmask[i];
        int bp=0,bc=0x7fffffff;
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
            cost=cost*2+gv;
            if(cost<bc){bc=cost;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
    // Analyze global state after greedy
    int G_max=0, worst_leaf=-1, worst_port=-1;
    int second_max=0;
    int at_max_count=0;
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
            if(fv>G_max){second_max=G_max;G_max=fv;worst_leaf=leaf;worst_port=pk;at_max_count=1;}
            else if(fv==G_max){at_max_count++;}
            else if(fv>second_max){second_max=fv;}
        }
    // Count flows on worst port
    int flows_on_worst=0;
    for(int i=0;i<fl_count;++i){
        if(fl_port[i]<0) continue;
        if((fl_sl[i]==worst_leaf||fl_dl[i]==worst_leaf)&&fl_port[i]==worst_port)
            flows_on_worst++;
    }
    int job_max=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk)
            for(int ph=0;ph<m;++ph){
                int o=out_load[leaf][pk][ph];if(o>job_max)job_max=o;
                int iv=in_load[leaf][pk][ph];if(iv>job_max)job_max=iv;
            }
    if(job_idx>=15)
        fprintf(stderr,"Job%d: G_max=%d 2nd=%d at_max=%d worst=(%d,%d) flows_on_worst=%d job_max=%d fl_count=%d\n",
            job_idx,G_max,second_max,at_max_count,worst_leaf,worst_port,flows_on_worst,job_max,fl_count);
    // update global
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int mo=0,mi=0;
            for(int ph=0;ph<m;++ph){if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];}
            global_out[leaf][pk]+=mo;global_in[leaf][pk]+=mi;
        }
    // Output (dummy)
    printf("%d\n",fl_count);
    for(int i=0;i<fl_count;++i){printf("%d %d %d",fl_src[i],fl_dst[i],fl_port[i]);if(i!=fl_count-1)printf(" ");}
    printf("\n");fflush(stdout);
}
int main(){
    memset(ht_key,-1,sizeof(ht_key));
    int n=fast_read_int();
    g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    for(int i=0;i<n;++i)solve_job(i);
    return 0;
}
