#include <stdio.h>
#include <string.h>

#if defined(_WIN32) || defined(_WIN64)
#define FAST_GET_CHAR getchar
#else
#define FAST_GET_CHAR getchar_unlocked
#endif

#define OUT_BUF_SIZE 1048576
char out_buf[OUT_BUF_SIZE];
int out_pos = 0;

inline void flush_out() {
    if (out_pos > 0) {
        fwrite(out_buf, 1, out_pos, stdout);
        out_pos = 0;
    }
}

inline void write_char(char c) {
    if (out_pos == OUT_BUF_SIZE) flush_out();
    out_buf[out_pos++] = c;
}

inline void fast_write(int x) {
    if (x < 0) { write_char('-'); x = -x; }
    if (x == 0) { write_char('0'); return; }
    char temp[12];
    int len = 0;
    while (x) { temp[len++] = (x % 10) + '0'; x /= 10; }
    while (len--) write_char(temp[len]);
}

inline int fast_read_int() {
    int c = FAST_GET_CHAR();
    while (c < '0' || c > '9') c = FAST_GET_CHAR();
    int x = 0;
    while (c >= '0' && c <= '9') { x = x * 10 + (c - '0'); c = FAST_GET_CHAR(); }
    return x;
}

#define MAX_NODES 13000
#define MAX_FLOWS 400000
#define BITSET_SIZE ((MAX_NODES * MAX_NODES) / 8 + 1)

unsigned char seen_bits[BITSET_SIZE];
int cleanup_list[MAX_FLOWS];
int cleanup_size;

int out_src[MAX_FLOWS];
int out_dst[MAX_FLOWS];
int out_port[MAX_FLOWS];
int out_size;

int g_l, g_p, g_r;
int leaf_counter[100]; // round-robin counter per source Leaf

void solve_job() {
    int m = fast_read_int();
    int f = fast_read_int();

    cleanup_size = 0;
    out_size = 0;
    memset(leaf_counter, 0, g_l * sizeof(int));

    for (int ph = 0; ph < m; ++ph) {
        for (int i = 0; i < f; ++i) {
            int src = fast_read_int();
            int dst = fast_read_int();

            int hash_idx = src * MAX_NODES + dst;
            int byte_idx = hash_idx >> 3;
            int bit_idx = hash_idx & 7;

            if (!(seen_bits[byte_idx] & (1 << bit_idx))) {
                seen_bits[byte_idx] |= (1 << bit_idx);
                cleanup_list[cleanup_size++] = hash_idx;

                int src_leaf = src / (g_p * g_r);
                int dst_leaf = dst / (g_p * g_r);
                int port;
                if (src_leaf == dst_leaf) {
                    port = -1;
                } else {
                    port = leaf_counter[src_leaf] % g_p;
                    leaf_counter[src_leaf]++;
                }
                out_src[out_size] = src;
                out_dst[out_size] = dst;
                out_port[out_size] = port;
                out_size++;
            }
        }
    }

    fast_write(out_size);
    write_char('\n');
    flush_out();
    fflush(stdout);
    for (int i = 0; i < out_size; ++i) {
        fast_write(out_src[i]); write_char(' ');
        fast_write(out_dst[i]); write_char(' ');
        fast_write(out_port[i]);
        if (i != out_size - 1) write_char(' ');
    }
    write_char('\n');
    flush_out();
    fflush(stdout);

    for (int i = 0; i < cleanup_size; ++i) {
        int h = cleanup_list[i];
        seen_bits[h >> 3] &= ~(1 << (h & 7));
    }
}

int main() {
    int n = fast_read_int();
    g_l = fast_read_int();
    g_p = fast_read_int();
    g_r = fast_read_int();

    for (int i = 0; i < n; ++i) {
        solve_job();
    }
    return 0;
}
