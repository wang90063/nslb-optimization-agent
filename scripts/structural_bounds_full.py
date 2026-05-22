#!/usr/bin/env python3
"""Structural lower bounds for all 5 NSLB scoring metrics."""
import sys, os, math
from collections import defaultdict


def parse_case(path):
    with open(path) as f:
        tokens = f.read().split()
    idx = 0
    def rd():
        nonlocal idx; v = int(tokens[idx]); idx += 1; return v
    n, l, p, r = rd(), rd(), rd(), rd()
    pr = p * r
    jobs = []
    total_flows = 0
    for _ in range(n):
        m, f = rd(), rd()
        po = defaultdict(int)
        pi = defaultdict(int)
        seen = set()
        il = 0
        for ph in range(m):
            seen.clear()
            for _ in range(f):
                src, dst = rd(), rd()
                if (src, dst, ph) in seen:
                    continue
                seen.add((src, dst, ph))
                sl, dl = src // pr, dst // pr
                if sl == dl:
                    continue
                po[(sl, ph)] += 1
                pi[(dl, ph)] += 1
                il += 1
        total_flows += il
        jobs.append({'m': m, 'f': f, 'po': dict(po), 'pi': dict(pi), 'il': il})
    return n, l, p, r, jobs, total_flows


def compute_bounds(n, l, p, r, jobs):
    # Maxsingler lb: max over jobs of ceil(max_phase_load / p)
    jm_lb = 0
    for job in jobs:
        for cnt in job['po'].values():
            v = math.ceil(cnt / p)
            if v > jm_lb: jm_lb = v
        for cnt in job['pi'].values():
            v = math.ceil(cnt / p)
            if v > jm_lb: jm_lb = v
    ms_lb = max(jm_lb / r, 1.0)
