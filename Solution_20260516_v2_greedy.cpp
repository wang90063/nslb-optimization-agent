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
inline void flush_out() {
    if (out_pos > 0) { fwrite(out_buf, 1, out_pos, stdout); out_pos = 0; }
}
inline void write_char(char c) {
    if (out_pos == OUT_BUF_SIZE) flush_out();
    out_buf[out_pos++] = c;
}
inline void fast_write(int x) {
    if (x < 0) { write_char('-'); x = -x; }
    if (x == 0) { write_char('0'); return; }
    char temp[12]; int len = 0;
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

#define MAX_CARDS 12800
#define MAX_FLOWS 400000
#define MAX_LEAFS 100
#define MAX_PORTS 32
#define MAX_PHASES 31
#define BITSET_SIZE ((MAX_CARDS * MAX_CARDS) / 8 + 1)

// --- dedup ---
static unsigned char seen_bits[BITSET_SIZE];
static int cleanup_list[MAX_FLOWS], cleanup_size;

// --- flow storage per job ---
static int fl_src[MAX_FLOWS], fl_dst[MAX_FLOWS];
static short fl_phase[MAX_FLOWS], fl_port[MAX_FLOWS];
static int fl_count;

// --- load tracking per job ---
static short out_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES]; // outgoing
static short in_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];  // incoming

// --- cross-job global state ---
static int global_out[MAX_LEAFS][MAX_PORTS];
static int global_in[MAX_LEAFS][MAX_PORTS];

// --- per-card grouping ---
static int card_fl_idx[MAX_FLOWS]; // flow indices sorted by src card
static int card_start[MAX_CARDS + 1]; // prefix sum for card grouping
static int tmp_pos[MAX_CARDS];

// --- greedy assignment ---
static int sort_buf[MAX_CARDS]; // cards to sort for a leaf
static int card_max_load[MAX_CARDS]; // max per-phase flow count for sorting

static int g_l, g_p, g_r, g_pr;

int cmp_desc(const void *a, const void *b) {
    return card_max_load[*(const int*)b] - card_max_load[*(const int*)a];
}

void solve_job() {
    int m = fast_read_int();
    int f = fast_read_int();

    cleanup_size = 0;
    fl_count = 0;
    int total_cards = g_l * g_pr;
    memset(card_start, 0, (total_cards + 1) * sizeof(int));

    // Phase 1: read all flows, dedup, store with phase info
    for (int ph = 0; ph < m; ++ph) {
        for (int i = 0; i < f; ++i) {
            int src = fast_read_int();
            int dst = fast_read_int();
            int hash_idx = src * MAX_CARDS + dst;
            int byte_idx = hash_idx >> 3;
            int bit_idx = hash_idx & 7;
            if (!(seen_bits[byte_idx] & (1 << bit_idx))) {
                seen_bits[byte_idx] |= (1 << bit_idx);
                cleanup_list[cleanup_size++] = hash_idx;
                fl_src[fl_count] = src;
                fl_dst[fl_count] = dst;
                fl_phase[fl_count] = (short)ph;
                card_start[src + 1]++;
                fl_count++;
            }
        }
    }

    // Phase 2: group flows by source card (counting sort)
    for (int i = 1; i <= total_cards; ++i)
        card_start[i] += card_start[i - 1];
    memcpy(tmp_pos, card_start, total_cards * sizeof(int));
    for (int i = 0; i < fl_count; ++i)
        card_fl_idx[tmp_pos[fl_src[i]]++] = i;

    // Phase 3: clear load arrays for this job
    memset(out_load, 0, g_l * sizeof(out_load[0]));
    memset(in_load, 0, g_l * sizeof(in_load[0]));

    // Phase 4: greedy port assignment per source leaf
    for (int leaf = 0; leaf < g_l; ++leaf) {
        int first_card = leaf * g_pr;
        int last_card = first_card + g_pr;
        int n_active = 0;

        // collect active cards on this leaf (those with inter-leaf flows)
        for (int card = first_card; card < last_card; ++card) {
            if (card_start[card + 1] == card_start[card]) continue;
            // check if card has any inter-leaf flows
            int has_inter = 0;
            int max_ph_load = 0;
            short ph_count[MAX_PHASES] = {};
            for (int j = card_start[card]; j < card_start[card + 1]; ++j) {
                int fi = card_fl_idx[j];
                int dst_leaf = fl_dst[fi] / g_pr;
                if (dst_leaf != leaf) {
                    has_inter = 1;
                    ph_count[fl_phase[fi]]++;
                }
            }
            if (!has_inter) {
                // all flows are intra-leaf, assign port -1
                for (int j = card_start[card]; j < card_start[card + 1]; ++j)
                    fl_port[card_fl_idx[j]] = -1;
                continue;
            }
            for (int ph = 0; ph < m; ++ph)
                if (ph_count[ph] > max_ph_load) max_ph_load = ph_count[ph];
            card_max_load[card] = max_ph_load;
            sort_buf[n_active++] = card;
        }

        // sort cards by max phase load descending (heaviest first)
        qsort(sort_buf, n_active, sizeof(int), cmp_desc);

        // assign each card to best port
        for (int ci = 0; ci < n_active; ++ci) {
            int card = sort_buf[ci];
            int best_port = 0;
            int best_cost = 0x7fffffff;

            for (int pk = 0; pk < g_p; ++pk) {
                int cost = 0;
                // simulate assigning card to port pk
                for (int j = card_start[card]; j < card_start[card + 1]; ++j) {
                    int fi = card_fl_idx[j];
                    int dst_leaf = fl_dst[fi] / g_pr;
                    if (dst_leaf == leaf) continue;
                    int ph = fl_phase[fi];
                    int o = out_load[leaf][pk][ph] + 1;
                    int in_v = in_load[dst_leaf][pk][ph] + 1;
                    int local_max = o > in_v ? o : in_v;
                    if (local_max > cost) cost = local_max;
                }
                // add global penalty (lighter weight)
                cost = cost * 4 + global_out[leaf][pk] + global_in[leaf][pk];
                if (cost < best_cost) {
                    best_cost = cost;
                    best_port = pk;
                }
            }

            // commit assignment
            for (int j = card_start[card]; j < card_start[card + 1]; ++j) {
                int fi = card_fl_idx[j];
                int dst_leaf = fl_dst[fi] / g_pr;
                if (dst_leaf == leaf) {
                    fl_port[fi] = -1;
                } else {
                    fl_port[fi] = (short)best_port;
                    int ph = fl_phase[fi];
                    out_load[leaf][best_port][ph]++;
                    in_load[dst_leaf][best_port][ph]++;
                }
            }
        }
    }

    // Phase 5: update global state
    for (int leaf = 0; leaf < g_l; ++leaf) {
        for (int pk = 0; pk < g_p; ++pk) {
            int max_out = 0, max_in = 0;
            for (int ph = 0; ph < m; ++ph) {
                if (out_load[leaf][pk][ph] > max_out) max_out = out_load[leaf][pk][ph];
                if (in_load[leaf][pk][ph] > max_in) max_in = in_load[leaf][pk][ph];
            }
            global_out[leaf][pk] += max_out;
            global_in[leaf][pk] += max_in;
        }
    }

    // Phase 6: output
    fast_write(fl_count);
    write_char('\n');
    flush_out();
    fflush(stdout);

    for (int i = 0; i < fl_count; ++i) {
        fast_write(fl_src[i]); write_char(' ');
        fast_write(fl_dst[i]); write_char(' ');
        fast_write(fl_port[i]);
        if (i != fl_count - 1) write_char(' ');
    }
    write_char('\n');
    flush_out();
    fflush(stdout);

    // cleanup bitset
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
    g_pr = g_p * g_r;

    for (int i = 0; i < n; ++i)
        solve_job();
    return 0;
}
