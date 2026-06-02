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
static int g_l,g_p,g_r,g_pr,g_n,g_job_idx;
static int fl_sl[MAX_FLOWS],fl_dl[MAX_FLOWS];
static int proj_out[MAX_LEAFS][MAX_PORTS];
static int proj_in[MAX_LEAFS][MAX_PORTS];

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
    for(int i=0;i<fl_count;++i){
        fl_sl[i]=fl_src[i]/g_pr;
        fl_dl[i]=fl_dst[i]/g_pr;
    }
    int gw = 1 + g_job_idx;
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
            int total=cost*2+gv*gw;
            if(total<bc){bc=total;bp=pk;}
        }
        fl_port[i]=(short)bp;
        unsigned int m2=mask;
        while(m2){int ph=__builtin_ctz(m2);out_load[sl][bp][ph]++;in_load[dl][bp][ph]++;m2&=m2-1;}
    }
    // Pass 2: local bottleneck swap
    int jmx=0;
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk)
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>jmx)jmx=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>jmx)jmx=in_load[leaf][pk][ph];
            }
    for(int iter=0;iter<20&&jmx>1;++iter){
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
                if(out_load[sl][cp][ph]==jmx||in_load[dl][cp][ph]==jmx){on_bn=1;break;}
                m2&=m2-1;
            }
            if(!on_bn) continue;
            int best_new=-1,best_new_max=jmx;
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
                improved=1;jmx=best_new_max;
            }
        }
        if(!improved) break;
    }
    // Pass 3: global-aware swap
    for(int leaf=0;leaf<g_l;++leaf)
        for(int pk=0;pk<g_p;++pk){
            int mo=0,mi=0;
            for(int ph=0;ph<m;++ph){
                if(out_load[leaf][pk][ph]>mo)mo=out_load[leaf][pk][ph];
                if(in_load[leaf][pk][ph]>mi)mi=in_load[leaf][pk][ph];
            }
            proj_out[leaf][pk]=global_out[leaf][pk]+mo;
            proj_in[leaf][pk]=global_in[leaf][pk]+mi;
        }
    for(int giter=0;giter<30;++giter){
        int gmx=0;
        for(int leaf=0;leaf<g_l;++leaf)
            for(int pk=0;pk<g_p;++pk){
                if(proj_out[leaf][pk]>gmx)gmx=proj_out[leaf][pk];
                if(proj_in[leaf][pk]>gmx)gmx=proj_in[leaf][pk];
            }
        if(gmx<=g_r) break;
        int improved=0;
        for(int i=0;i<fl_count&&!improved;++i){
            int sl=fl_sl[i],dl=fl_dl[i];
            if(sl==dl) continue;
            int cp=fl_port[i];
            unsigned int mask=fl_pmask[i];
            if(proj_out[sl][cp]!=gmx&&proj_in[dl][cp]!=gmx) continue;
            int best_pk=-1,best_score=gmx;
            for(int pk=0;pk<g_p;++pk){
                if(pk==cp) continue;
                int local_ok=1;
                unsigned int m2=mask;
                while(m2){
                    int ph=__builtin_ctz(m2);
                    if(out_load[sl][pk][ph]+1>g_r||in_load[dl][pk][ph]+1>g_r){local_ok=0;break;}
                    m2&=m2-1;
                }
                if(!local_ok) continue;
                int new_mo_cp=0,new_mi_cp=0,new_mo_pk=0,new_mi_pk=0;
                unsigned int m3=mask;
                while(m3){
                    int ph=__builtin_ctz(m3);
                    int oo=out_load[sl][cp][ph]-1;if(oo>new_mo_cp)new_mo_cp=oo;
                    int oi=in_load[dl][cp][ph]-1;if(oi>new_mi_cp)new_mi_cp=oi;
                    int no=out_load[sl][pk][ph]+1;if(no>new_mo_pk)new_mo_pk=no;
                    int ni=in_load[dl][pk][ph]+1;if(ni>new_mi_pk)new_mi_pk=ni;
                    m3&=m3-1;
                }
                for(int ph=0;ph<m;++ph){
                    if(mask&(1u<<ph)) continue;
                    if(out_load[sl][cp][ph]>new_mo_cp)new_mo_cp=out_load[sl][cp][ph];
                    if(in_load[dl][cp][ph]>new_mi_cp)new_mi_cp=in_load[dl][cp][ph];
                    if(out_load[sl][pk][ph]>new_mo_pk)new_mo_pk=out_load[sl][pk][ph];
                    if(in_load[dl][pk][ph]>new_mi_pk)new_mi_pk=in_load[dl][pk][ph];
                }
                int old_mo_pk=0,old_mi_pk=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[sl][pk][ph]>old_mo_pk)old_mo_pk=out_load[sl][pk][ph];
                    if(in_load[dl][pk][ph]>old_mi_pk)old_mi_pk=in_load[dl][pk][ph];
                }
                int npo_cp=global_out[sl][cp]-(proj_out[sl][cp]-global_out[sl][cp])+new_mo_cp;
                int npi_cp=global_in[dl][cp]-(proj_in[dl][cp]-global_in[dl][cp])+new_mi_cp;
                int npo_pk=global_out[sl][pk]-old_mo_pk+new_mo_pk;
                int npi_pk=global_in[dl][pk]-old_mi_pk+new_mi_pk;
                int ns=npo_cp;if(npi_cp>ns)ns=npi_cp;if(npo_pk>ns)ns=npo_pk;if(npi_pk>ns)ns=npi_pk;
                if(ns<best_score){best_score=ns;best_pk=pk;}
            }
            // PLACEHOLDER_APPLY_SWAP
            if(best_pk>=0){
                unsigned int m2=mask;
                while(m2){int ph=__builtin_ctz(m2);out_load[sl][cp][ph]--;in_load[dl][cp][ph]--;out_load[sl][best_pk][ph]++;in_load[dl][best_pk][ph]++;m2&=m2-1;}
                fl_port[i]=(short)best_pk;
                int mo_cp=0,mi_cp=0,mo_pk=0,mi_pk=0;
                for(int ph=0;ph<m;++ph){
                    if(out_load[sl][cp][ph]>mo_cp)mo_cp=out_load[sl][cp][ph];
                    if(in_load[dl][cp][ph]>mi_cp)mi_cp=in_load[dl][cp][ph];
                    if(out_load[sl][best_pk][ph]>mo_pk)mo_pk=out_load[sl][best_pk][ph];
                    if(in_load[dl][best_pk][ph]>mi_pk)mi_pk=in_load[dl][best_pk][ph];
                }
                proj_out[sl][cp]=global_out[sl][cp]+mo_cp;
                proj_in[dl][cp]=global_in[dl][cp]+mi_cp;
                proj_out[sl][best_pk]=global_out[sl][best_pk]+mo_pk;
                proj_in[dl][best_pk]=global_in[dl][best_pk]+mi_pk;
                improved=1;
            }
        }
        if(!improved) break;
    }
    // PLACEHOLDER_FINAL
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
    g_job_idx++;
}

int main(){
    memset(ht_key,-1,sizeof(ht_key));
    g_n=fast_read_int();
    g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    g_job_idx=0;
    for(int i=0;i<g_n;++i)solve_job();
    return 0;
}
