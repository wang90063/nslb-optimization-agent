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
#define HARD_DEADLINE_MS 3500.0

static unsigned char seen_bits[BITSET_SIZE];
static int cleanup_list[MAX_FLOWS],cleanup_size;
static int fl_src[MAX_FLOWS],fl_dst[MAX_FLOWS];
static short fl_phase[MAX_FLOWS],fl_port[MAX_FLOWS];
static int fl_count;
static short out_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short in_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static int global_out[MAX_LEAFS][MAX_PORTS];
static int global_in[MAX_LEAFS][MAX_PORTS];
static int card_fl_idx[MAX_FLOWS];
static int card_start[MAX_CARDS+1];
static int tmp_pos[MAX_CARDS];
static int sort_buf[MAX_CARDS];
static int card_max_load[MAX_CARDS];
static short card_out_count[MAX_CARDS*MAX_PHASES];
struct InEntry{short dst_leaf,phase,count;};
static InEntry in_entries[MAX_FLOWS];
static int in_entry_start[MAX_CARDS+1];
static int in_entry_total;
static short card_assigned_port[MAX_CARDS];
static int active_list[MAX_CARDS];
static int n_active_total;
static int g_l,g_p,g_r,g_pr;
static double g_start_ms;

int cmp_desc(const void*a,const void*b){return card_max_load[*(const int*)b]-card_max_load[*(const int*)a];}
static unsigned int rng=98765;
inline unsigned int xorshift(){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
inline double now_ms(){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000.0+t.tv_nsec/1e6;}

void solve_job(double deadline_from_start){
    int m=fast_read_int(),f=fast_read_int();
    cleanup_size=0;fl_count=0;
    int total_cards=g_l*g_pr;
    memset(card_start,0,(total_cards+1)*sizeof(int));

    for(int ph=0;ph<m;++ph)
        for(int i=0;i<f;++i){
            int src=fast_read_int(),dst=fast_read_int();
            int hi=src*MAX_CARDS+dst,by=hi>>3,bi=hi&7;
            if(!(seen_bits[by]&(1<<bi))){
                seen_bits[by]|=(1<<bi);
                cleanup_list[cleanup_size++]=hi;
                fl_src[fl_count]=src;fl_dst[fl_count]=dst;
                fl_phase[fl_count]=(short)ph;card_start[src+1]++;fl_count++;
            }
        }

    for(int i=1;i<=total_cards;++i)card_start[i]+=card_start[i-1];
    memcpy(tmp_pos,card_start,total_cards*sizeof(int));
    for(int i=0;i<fl_count;++i)card_fl_idx[tmp_pos[fl_src[i]]++]=i;
    memset(out_load,0,g_l*sizeof(out_load[0]));
    memset(in_load,0,g_l*sizeof(in_load[0]));

    n_active_total=0;in_entry_total=0;
    static char dst_seen[MAX_LEAFS];
    static int dst_list[MAX_LEAFS];
    static short dst_ph_cnt[MAX_LEAFS*MAX_PHASES];

    for(int leaf=0;leaf<g_l;++leaf){
        int fc=leaf*g_pr,lc=fc+g_pr,na=0;
        for(int card=fc;card<lc;++card){
            if(card_start[card+1]==card_start[card])continue;
            int has_inter=0,max_ph=0,nd=0;
            short*oc=&card_out_count[card*MAX_PHASES];
            memset(oc,0,m*sizeof(short));
            for(int j=card_start[card];j<card_start[card+1];++j){
                int fi=card_fl_idx[j],dl=fl_dst[fi]/g_pr;
                if(dl==leaf)continue;
                has_inter=1;oc[fl_phase[fi]]++;
                if(!dst_seen[dl]){dst_seen[dl]=1;dst_list[nd++]=dl;}
                dst_ph_cnt[dl*MAX_PHASES+fl_phase[fi]]++;
            }
            if(!has_inter){for(int j=card_start[card];j<card_start[card+1];++j)fl_port[card_fl_idx[j]]=-1;continue;}
            for(int ph=0;ph<m;++ph)if(oc[ph]>max_ph)max_ph=oc[ph];
            card_max_load[card]=max_ph;
            in_entry_start[n_active_total]=in_entry_total;
            for(int di=0;di<nd;++di){
                int dl=dst_list[di];
                for(int ph=0;ph<m;++ph){int idx=dl*MAX_PHASES+ph;if(dst_ph_cnt[idx]){in_entries[in_entry_total++]={(short)dl,(short)ph,dst_ph_cnt[idx]};dst_ph_cnt[idx]=0;}}
                dst_seen[dl]=0;
            }
            sort_buf[na++]=card;active_list[n_active_total++]=card;
        }
        qsort(sort_buf,na,sizeof(int),cmp_desc);
        for(int ci=0;ci<na;++ci){
            int card=sort_buf[ci],bp=0,bc=0x7fffffff;
            for(int pk=0;pk<g_p;++pk){
                int cost=0;
                for(int j=card_start[card];j<card_start[card+1];++j){
                    int fi=card_fl_idx[j],dl=fl_dst[fi]/g_pr;
                    if(dl==leaf)continue;
                    int o=out_load[leaf][pk][fl_phase[fi]]+1,iv=in_load[dl][pk][fl_phase[fi]]+1;
                    int v=o>iv?o:iv;if(v>cost)cost=v;
                }
                cost=cost*4+global_out[leaf][pk]+global_in[leaf][pk];
                if(cost<bc){bc=cost;bp=pk;}
            }
            card_assigned_port[card]=(short)bp;
            for(int j=card_start[card];j<card_start[card+1];++j){
                int fi=card_fl_idx[j],dl=fl_dst[fi]/g_pr;
                if(dl==leaf)fl_port[fi]=-1;
                else{fl_port[fi]=(short)bp;out_load[leaf][bp][fl_phase[fi]]++;in_load[dl][bp][fl_phase[fi]]++;}
            }
        }
    }
    in_entry_start[n_active_total]=in_entry_total;

    // LOCAL SEARCH
    if(n_active_total>1){
        int iter=0;
        while(1){
            if(++iter%256==0&&now_ms()-g_start_ms>=deadline_from_start)break;
            int idx=xorshift()%n_active_total;
            int card=active_list[idx],leaf=card/g_pr,cp=card_assigned_port[card];
            short*oc=&card_out_count[card*MAX_PHASES];
            int ies=in_entry_start[idx],iee=in_entry_start[idx+1];
            int bpk=-1;long long bd=0;
            for(int pk=0;pk<g_p;++pk){
                if(pk==cp)continue;
                long long d=0;
                for(int ph=0;ph<m;++ph){int cnt=oc[ph];if(!cnt)continue;int ov=out_load[leaf][cp][ph],nv=out_load[leaf][pk][ph];for(int k=0;k<cnt;++k){int a=ov-k,b=nv+k+1;if(a>g_r)d-=2*(a-g_r)-1;if(b>g_r)d+=2*(b-g_r)-1;}}
                for(int ie=ies;ie<iee;++ie){int dl=in_entries[ie].dst_leaf,ph=in_entries[ie].phase,cnt=in_entries[ie].count;int ov=in_load[dl][cp][ph],nv=in_load[dl][pk][ph];for(int k=0;k<cnt;++k){int a=ov-k,b=nv+k+1;if(a>g_r)d-=2*(a-g_r)-1;if(b>g_r)d+=2*(b-g_r)-1;}}
                if(d<bd){bd=d;bpk=pk;}
            }
            if(bpk>=0){
                for(int ph=0;ph<m;++ph){int cnt=oc[ph];if(cnt){out_load[leaf][cp][ph]-=cnt;out_load[leaf][bpk][ph]+=cnt;}}
                for(int ie=ies;ie<iee;++ie){in_load[in_entries[ie].dst_leaf][cp][in_entries[ie].phase]-=in_entries[ie].count;in_load[in_entries[ie].dst_leaf][bpk][in_entries[ie].phase]+=in_entries[ie].count;}
                card_assigned_port[card]=(short)bpk;
                for(int j=card_start[card];j<card_start[card+1];++j){int fi=card_fl_idx[j];if(fl_dst[fi]/g_pr!=leaf)fl_port[fi]=(short)bpk;}
            }
        }
    }

    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int mo=0,mi=0;
            for(int ph=0;ph<m;++ph){if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];}
            global_out[leaf][pk]+=mo;global_in[leaf][pk]+=mi;
        }

    fast_write(fl_count);write_char('\n');flush_out();fflush(stdout);
    for(int i=0;i<fl_count;++i){fast_write(fl_src[i]);write_char(' ');fast_write(fl_dst[i]);write_char(' ');fast_write(fl_port[i]);if(i!=fl_count-1)write_char(' ');}
    write_char('\n');flush_out();fflush(stdout);
    for(int i=0;i<cleanup_size;++i){int h=cleanup_list[i];seen_bits[h>>3]&=~(1<<(h&7));}
}

int main(){
    g_start_ms=now_ms();
    int n=fast_read_int();
    g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    for(int i=0;i<n;++i){
        double elapsed=now_ms()-g_start_ms;
        double remaining=HARD_DEADLINE_MS-elapsed;
        if(remaining<0)remaining=0;
        double my_deadline=elapsed+remaining/(n-i);
        solve_job(my_deadline);
    }
    return 0;
}
