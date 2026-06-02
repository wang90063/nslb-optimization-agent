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
#define BITSET_SIZE ((MAX_CARDS*MAX_CARDS)/8+1)
static unsigned char seen_bits[BITSET_SIZE];
static int cleanup_list[MAX_FLOWS],cleanup_size;
static int fl_src[MAX_FLOWS],fl_dst[MAX_FLOWS];
static short fl_port[MAX_FLOWS];
static int fl_count,g_l,g_p,g_r,g_pr;
void solve_job(){
    int m=fast_read_int(),f=fast_read_int();
    fl_count=0;cleanup_size=0;
    for(int ph=0;ph<m;++ph)
        for(int i=0;i<f;++i){
            int src=fast_read_int(),dst=fast_read_int();
            int hi=src*MAX_CARDS+dst,by=hi>>3,bi=hi&7;
            if(!(seen_bits[by]&(1<<bi))){
                seen_bits[by]|=(1<<bi);cleanup_list[cleanup_size++]=hi;
                fl_src[fl_count]=src;fl_dst[fl_count]=dst;
                int sl=src/g_pr,dl=dst/g_pr;
                if(sl==dl)fl_port[fl_count]=-1;
                else{unsigned int h=(unsigned int)(src*2654435761u^dst*2246822519u);h=((h>>16)^h)*0x45d9f3b;h=(h>>16)^h;fl_port[fl_count]=(short)(h%g_p);}
                fl_count++;
            }
        }
    for(int i=0;i<cleanup_size;++i){int h=cleanup_list[i];seen_bits[h>>3]&=~(1<<(h&7));}
    fast_write(fl_count);write_char('\n');flush_out();fflush(stdout);
    for(int i=0;i<fl_count;++i){fast_write(fl_src[i]);write_char(' ');fast_write(fl_dst[i]);write_char(' ');fast_write(fl_port[i]);if(i!=fl_count-1)write_char(' ');}
    write_char('\n');flush_out();fflush(stdout);
}
int main(){
    int n=fast_read_int();g_l=fast_read_int();g_p=fast_read_int();g_r=fast_read_int();g_pr=g_p*g_r;
    for(int i=0;i<n;++i)solve_job();
    return 0;
}
