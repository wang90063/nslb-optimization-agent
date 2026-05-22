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
static int fl_order[MAX_FLOWS];
static int fl_tmp[MAX_FLOWS];

static short out_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short in_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static int global_out[MAX_LEAFS][MAX_PORTS];
static int global_in[MAX_LEAFS][MAX_PORTS];
static int g_l,g_p,g_r,g_pr,g_n;

static struct timespec ts_start;
inline long elapsed_ms(){
    struct timespec now;clock_gettime(CLOCK_MONOTONIC,&now);
    return (now.tv_sec-ts_start.tv_sec)*1000+(now.tv_nsec-ts_start.tv_nsec)/1000000;
}

void sort_flows_by_popcount(){
    int buckets[32]={};
    for(int i=0;i<fl_count;++i) buckets[__builtin_popcount(fl_pmask[i])]++;
    int offsets[32]; offsets[31]=0;
    for(int i=30;i>=0;--i) offsets[i]=offsets[i+1]+buckets[i+1];
    for(int i=0;i<fl_count;++i){
        int pc=__builtin_popcount(fl_pmask[i]);
        fl_order[offsets[pc]++]=i;
    }
}

void do_greedy(int m){
    memset(out_load,0,g_l*sizeof(out_load[0]));
    memset(in_load,0,g_l*sizeof(in_load[0]));
    for(int ii=0;ii<fl_count;++ii){
        int i=fl_order[ii];
        int src=fl_src[i],dst=fl_dst[i];
        int sl=src/g_pr,dl=dst/g_pr;
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
            cost=cost*4+global_out[sl][pk]+global_in[dl][pk];
            if(cost<bc){bc=cost;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
}

int compute_max_load(int m){
    int mx=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk)
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>mx)mx=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>mx)mx=in_load[leaf][pk][ph];
            }
    return mx;
}

void iterative_improve(int m, long time_budget_ms){
    int max_load=compute_max_load(m);
    if(max_load<=1) return;
    long deadline=elapsed_ms()+time_budget_ms;

    while(elapsed_ms()<deadline){
        int found_improvement=0;
        for(int leaf=0;leaf<g_l&&!found_improvement;++leaf)
          for(int pk=0;pk<g_p&&!found_improvement;++pk)
            for(int ph=0;ph<m&&!found_improvement;++ph){
              for(int dir=0;dir<2&&!found_improvement;++dir){
                short val=(dir==0)?out_load[leaf][pk][ph]:in_load[leaf][pk][ph];
                if(val!=max_load) continue;
                // find best flow to move off this cell
                int best_fi=-1,best_np=-1,best_cost=0x7fffffff;
                for(int i=0;i<fl_count;++i){
                    if(fl_port[i]!=pk) continue;
                    if(!(fl_pmask[i]&(1u<<ph))) continue;
                    int sl=fl_src[i]/g_pr,dl=fl_dst[i]/g_pr;
                    if(sl==dl) continue;
                    if(dir==0&&sl!=leaf) continue;
                    if(dir==1&&dl!=leaf) continue;
                    unsigned int mask=fl_pmask[i];
                    for(int np=0;np<g_p;++np){
                        if(np==pk) continue;
                        int ok=1,worst=0;
                        unsigned int m2=mask;
                        while(m2){
                            int p2=__builtin_ctz(m2);
                            int no=out_load[sl][np][p2]+1;
                            int ni=in_load[dl][np][p2]+1;
                            if(no>=max_load||ni>=max_load){ok=0;break;}
                            if(no>worst)worst=no;
                            if(ni>worst)worst=ni;
                            m2&=m2-1;
                        }
                        if(ok&&worst<best_cost){
                            best_cost=worst;best_fi=i;best_np=np;
                        }
                    }
                }
                if(best_fi>=0){
                    int i=best_fi,np=best_np;
                    int sl=fl_src[i]/g_pr,dl=fl_dst[i]/g_pr;
                    unsigned int m2=fl_pmask[i];
                    while(m2){
                        int p2=__builtin_ctz(m2);
                        out_load[sl][pk][p2]--;in_load[dl][pk][p2]--;
                        out_load[sl][np][p2]++;in_load[dl][np][p2]++;
                        m2&=m2-1;
                    }
                    fl_port[best_fi]=(short)best_np;
                    found_improvement=1;
                }
              }
            }
        if(!found_improvement) break;
        max_load=compute_max_load(m);
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

    for(int i=0;i<ht_used_cnt;++i){
        int hi=ht_key[ht_used[i]];
        seen_bits[hi>>3]&=~(1<<(hi&7));
    }

    sort_flows_by_popcount();
    do_greedy(m);

    long budget=100;
    if(g_n<=10) budget=400;
    else if(g_n<=20) budget=200;
    iterative_improve(m, budget);

    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int mo=0,mi=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
            }
            global_out[leaf][pk]+=mo;global_in[leaf][pk]+=mi;
        }

    fast_write(fl_count);write_char('\n');flush_out();fflush(stdout);
    for(int i=0;i<fl_count;++i){
        fast_write(fl_src[i]);write_char(' ');
        fast_write(fl_dst[i]);write_char(' ');
        fast_write(fl_port[i]);
        if(i!=fl_count-1)write_char(' ');
    }
    write_char('\n');flush_out();fflush(stdout);
}

int main(){
    clock_gettime(CLOCK_MONOTONIC,&ts_start);
    memset(ht_key,-1,sizeof(ht_key));
    g_n=fast_read_int();
    g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    for(int i=0;i<g_n;++i) solve_job();
    return 0;
}
