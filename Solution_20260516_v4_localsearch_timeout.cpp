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

static unsigned char seen_bits[BITSET_SIZE];
static int cleanup_list[MAX_FLOWS], cleanup_size;

static int fl_src[MAX_FLOWS], fl_dst[MAX_FLOWS];
static short fl_phase[MAX_FLOWS], fl_port[MAX_FLOWS];
static int fl_count;

static short out_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static short in_load[MAX_LEAFS][MAX_PORTS][MAX_PHASES];
static int global_out[MAX_LEAFS][MAX_PORTS];
static int global_in[MAX_LEAFS][MAX_PORTS];

static int card_fl_idx[MAX_FLOWS];
static int card_start[MAX_CARDS + 1];
static int tmp_pos[MAX_CARDS];
static int sort_buf[MAX_CARDS];
static int card_max_load[MAX_CARDS];

// per-card compact metadata for local search
// card_out_count[card * MAX_PHASES + ph] = outgoing inter-leaf flows in phase ph
static short card_out_count[MAX_CARDS * MAX_PHASES];
// incoming info stored as compact list per card
struct InEntry { short dst_leaf; short phase; short count; };
static InEntry in_entries[MAX_FLOWS]; // shared pool
static int in_entry_start[MAX_CARDS + 1]; // index into in_entries per card
static int in_entry_total;

static short card_assigned_port[MAX_CARDS];
static int active_list[MAX_CARDS];
static int n_active_total;

static int g_l, g_p, g_r, g_pr;
static struct timespec ts_start;

static inline double elapsed_ms() {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - ts_start.tv_sec) * 1000.0 + (now.tv_nsec - ts_start.tv_nsec) / 1e6;
}

int cmp_desc(const void *a, const void *b) {
    return card_max_load[*(const int*)b] - card_max_load[*(const int*)a];
}

static unsigned int rng = 98765;
inline unsigned int xorshift() {
    rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng;
}

void solve_job(double deadline_ms) {
    int m = fast_read_int();
    int f = fast_read_int();

    cleanup_size = 0;
    fl_count = 0;
    int total_cards = g_l * g_pr;
    memset(card_start, 0, (total_cards + 1) * sizeof(int));

    for (int ph = 0; ph < m; ++ph) {
        for (int i = 0; i < f; ++i) {
            int src = fast_read_int(), dst = fast_read_int();
            int hash_idx = src * MAX_CARDS + dst;
            int byte_idx = hash_idx >> 3, bit_idx = hash_idx & 7;
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

    for (int i = 1; i <= total_cards; ++i) card_start[i] += card_start[i - 1];
    memcpy(tmp_pos, card_start, total_cards * sizeof(int));
    for (int i = 0; i < fl_count; ++i) card_fl_idx[tmp_pos[fl_src[i]]++] = i;

    memset(out_load, 0, g_l * sizeof(out_load[0]));
    memset(in_load, 0, g_l * sizeof(in_load[0]));

    // === GREEDY + build metadata ===
    n_active_total = 0;
    in_entry_total = 0;
    memset(card_out_count, 0, total_cards * MAX_PHASES * sizeof(short));

    // temp for building in_entries per card
    static char dst_seen[MAX_LEAFS];
    static int dst_list[MAX_LEAFS];
    static short dst_ph_cnt[MAX_LEAFS * MAX_PHASES];

    for (int leaf = 0; leaf < g_l; ++leaf) {
        int first_card = leaf * g_pr, last_card = first_card + g_pr;
        int n_active = 0;

        for (int card = first_card; card < last_card; ++card) {
            if (card_start[card + 1] == card_start[card]) continue;
            int has_inter = 0, max_ph = 0;
            short *out_c = &card_out_count[card * MAX_PHASES];
            int n_dst = 0;

            for (int j = card_start[card]; j < card_start[card + 1]; ++j) {
                int fi = card_fl_idx[j];
                int dl = fl_dst[fi] / g_pr;
                if (dl == leaf) continue;
                has_inter = 1;
                int ph = fl_phase[fi];
                out_c[ph]++;
                if (!dst_seen[dl]) { dst_seen[dl] = 1; dst_list[n_dst++] = dl; }
                dst_ph_cnt[dl * MAX_PHASES + ph]++;
            }

            if (!has_inter) {
                for (int j = card_start[card]; j < card_start[card + 1]; ++j)
                    fl_port[card_fl_idx[j]] = -1;
                card_assigned_port[card] = -1;
                continue;
            }

            for (int ph = 0; ph < m; ++ph)
                if (out_c[ph] > max_ph) max_ph = out_c[ph];
            card_max_load[card] = max_ph;

            // store in_entries for this card
            in_entry_start[n_active_total] = in_entry_total;
            for (int di = 0; di < n_dst; ++di) {
                int dl = dst_list[di];
                for (int ph = 0; ph < m; ++ph) {
                    int idx = dl * MAX_PHASES + ph;
                    if (dst_ph_cnt[idx]) {
                        in_entries[in_entry_total].dst_leaf = (short)dl;
                        in_entries[in_entry_total].phase = (short)ph;
                        in_entries[in_entry_total].count = dst_ph_cnt[idx];
                        in_entry_total++;
                        dst_ph_cnt[idx] = 0;
                    }
                }
                dst_seen[dl] = 0;
            }

            sort_buf[n_active++] = card;
            active_list[n_active_total++] = card;
        }

        // sort for greedy
        int greedy_start = n_active_total - n_active;
        qsort(sort_buf, n_active, sizeof(int), cmp_desc);

        for (int ci = 0; ci < n_active; ++ci) {
            int card = sort_buf[ci];
            int best_port = 0, best_cost = 0x7fffffff;

            for (int pk = 0; pk < g_p; ++pk) {
                int cost = 0;
                for (int j = card_start[card]; j < card_start[card + 1]; ++j) {
                    int fi = card_fl_idx[j];
                    int dl = fl_dst[fi] / g_pr;
                    if (dl == leaf) continue;
                    int ph = fl_phase[fi];
                    int o = out_load[leaf][pk][ph] + 1;
                    int iv = in_load[dl][pk][ph] + 1;
                    int v = o > iv ? o : iv;
                    if (v > cost) cost = v;
                }
                cost = cost * 4 + global_out[leaf][pk] + global_in[leaf][pk];
                if (cost < best_cost) { best_cost = cost; best_port = pk; }
            }

            card_assigned_port[card] = (short)best_port;
            for (int j = card_start[card]; j < card_start[card + 1]; ++j) {
                int fi = card_fl_idx[j];
                int dl = fl_dst[fi] / g_pr;
                if (dl == leaf) fl_port[fi] = -1;
                else {
                    fl_port[fi] = (short)best_port;
                    out_load[leaf][best_port][fl_phase[fi]]++;
                    in_load[dl][best_port][fl_phase[fi]]++;
                }
            }
        }
    }
    in_entry_start[n_active_total] = in_entry_total;

    // === LOCAL SEARCH: minimize sum of max(0, load-r)^2 ===
    if (n_active_total > 1) {
        int check_interval = 256;
        int iter = 0;
        while (1) {
            if (++iter % check_interval == 0 && elapsed_ms() >= deadline_ms) break;

            int idx = xorshift() % n_active_total;
            int card = active_list[idx];
            int leaf = card / g_pr;
            int cur_port = card_assigned_port[card];
            short *out_c = &card_out_count[card * MAX_PHASES];
            int ie_s = in_entry_start[idx], ie_e = in_entry_start[idx + 1];

            int best_pk = -1;
            long long best_delta = 0;

            for (int pk = 0; pk < g_p; ++pk) {
                if (pk == cur_port) continue;
                long long delta = 0;

                // outgoing delta
                for (int ph = 0; ph < m; ++ph) {
                    int cnt = out_c[ph];
                    if (!cnt) continue;
                    int old_v = out_load[leaf][cur_port][ph];
                    int new_v = out_load[leaf][pk][ph];
                    // remove cnt from old
                    for (int k = 0; k < cnt; ++k) {
                        int a = old_v - k, b = new_v + k + 1;
                        if (a > g_r) { int d = a-g_r; delta -= 2*d - 1; }
                        if (b > g_r) { int d = b-g_r; delta += 2*d - 1; }
                    }
                }

                // incoming delta
                for (int ie = ie_s; ie < ie_e; ++ie) {
                    int dl = in_entries[ie].dst_leaf;
                    int ph = in_entries[ie].phase;
                    int cnt = in_entries[ie].count;
                    int old_v = in_load[dl][cur_port][ph];
                    int new_v = in_load[dl][pk][ph];
                    for (int k = 0; k < cnt; ++k) {
                        int a = old_v - k, b = new_v + k + 1;
                        if (a > g_r) { int d = a-g_r; delta -= 2*d - 1; }
                        if (b > g_r) { int d = b-g_r; delta += 2*d - 1; }
                    }
                }

                if (delta < best_delta) { best_delta = delta; best_pk = pk; }
            }

            if (best_pk >= 0) {
                // apply move
                for (int ph = 0; ph < m; ++ph) {
                    int cnt = out_c[ph];
                    if (!cnt) continue;
                    out_load[leaf][cur_port][ph] -= cnt;
                    out_load[leaf][best_pk][ph] += cnt;
                }
                for (int ie = ie_s; ie < ie_e; ++ie) {
                    int dl = in_entries[ie].dst_leaf;
                    int ph = in_entries[ie].phase;
                    int cnt = in_entries[ie].count;
                    in_load[dl][cur_port][ph] -= cnt;
                    in_load[dl][best_pk][ph] += cnt;
                }
                card_assigned_port[card] = (short)best_pk;
                for (int j = card_start[card]; j < card_start[card + 1]; ++j) {
                    int fi = card_fl_idx[j];
                    if (fl_dst[fi] / g_pr != leaf)
                        fl_port[fi] = (short)best_pk;
                }
            }
        }
    }

    // update global
    for (int leaf = 0; leaf < g_l; ++leaf)
        for (int pk = 0; pk < g_p; ++pk) {
            int mx_out = 0, mx_in = 0;
            for (int ph = 0; ph < m; ++ph) {
                if (out_load[leaf][pk][ph] > mx_out) mx_out = out_load[leaf][pk][ph];
                if (in_load[leaf][pk][ph] > mx_in) mx_in = in_load[leaf][pk][ph];
            }
            global_out[leaf][pk] += mx_out;
            global_in[leaf][pk] += mx_in;
        }

    // output
    fast_write(fl_count); write_char('\n');
    flush_out(); fflush(stdout);
    for (int i = 0; i < fl_count; ++i) {
        fast_write(fl_src[i]); write_char(' ');
        fast_write(fl_dst[i]); write_char(' ');
        fast_write(fl_port[i]);
        if (i != fl_count - 1) write_char(' ');
    }
    write_char('\n'); flush_out(); fflush(stdout);

    for (int i = 0; i < cleanup_size; ++i) {
        int h = cleanup_list[i];
        seen_bits[h >> 3] &= ~(1 << (h & 7));
    }
}

int main() {
    clock_gettime(CLOCK_MONOTONIC, &ts_start);
    int n = fast_read_int();
    g_l = fast_read_int();
    g_p = fast_read_int();
    g_r = fast_read_int();
    g_pr = g_p * g_r;

    double budget = 4000.0; // 4s, leave 1s for compile + safety
    double per_job = budget / n;

    for (int i = 0; i < n; ++i) {
        double deadline = (i + 1) * per_job;
        solve_job(deadline);
    }
    return 0;
}
