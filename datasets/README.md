# Dataset Tiers

This directory defines the current local data criterion in three layers.

## `submit_core.txt`

Use this set to decide whether a version is worth submitting.

Current composition:
- `proxy_1..9`: the historically strongest online-aligned backbone (`comp + online_sim`)
- `proxy_10`: promoted from contrast after `v94` online failure; currently the clearest
  moderate `p=16` case that agrees with the `v87 > v94` online direction
- `medium_25 / 32`: currently retained as the more stable medium anchors
- `bench_15`: the clearest active bench anchor for the same gain pattern

This set is intentionally conservative. It prefers cases with repeated
agreement across `v62 / v77 / v87` over broader but noisier family totals.

## `contrast.txt`

Use this set to diagnose *why* a version moved, not to decide submission by
itself.

Current composition:
- `bench_1`: known local-repair trap
- `bench_16`: adjacent moderate bench splitter
- `medium_31`: local splitter that helped `v93`, but was not confirmed by the
  `365.60` online result
- `proxy_11 / 12`: new proxy cases that still separate local branches, but have
  not yet shown stable online alignment strong enough to own the submit decision

If a rule only wins here but not on `submit_core`, treat it as unresolved.

## `guardrail.txt`

Use this set only to block bad versions.

Current composition:
- all `hard_*`
- all `ai_*`

These cases are still valuable, but current evidence says they should guard
against blow-ups, not drive the submit ranking.

## `lowr_diagnostic.txt`

Use this set as a temporary microscope for the current `r<=3` research line.

Planned composition:
- low-`r` cases with `jm==r+1` or only a few overload cells
- `total ≈ p*r` boundary cases that amplify greedy / repair differences
- `p>=16`, multi-phase low-`r` cases that are closer to the suspected online gap
- hard-feasible `r=2` families in the style of `param_extreme_r2`

Current `v0` status:
- existing anchors: `param_extreme_r2 / param_r2_p32_hot / param_r3_hot / medium_31`
- newly promoted safe cases: `lowr_1 / 4 / 7 / 8 / 10`
- generated but currently excluded for runtime: `lowr_2 / 3 / 5 / 6 / 9`

Important:
- This is **not** part of submit/no-submit decision by default.
- Promote only the cases that later show stable alignment with online results.

## Commands

Score one tier:

```bash
python3 scripts/score_manifest.py ./solver datasets/submit_core.txt
python3 scripts/score_manifest.py ./solver datasets/contrast.txt
python3 scripts/score_manifest.py ./solver datasets/guardrail.txt
```

Compare multiple versions at once:

```bash
python3 scripts/compare_manifests.py \
  datasets/submit_core.txt datasets/contrast.txt datasets/guardrail.txt \
  -- /tmp/v62_cmp /tmp/v77_cmp /tmp/v87_cmp /tmp/v94_cmp
```

Suggested submit workflow:

1. Rank candidate versions on `submit_core`
2. Read `contrast` to understand which branch behavior changed
3. Reject versions that fail `guardrail`
4. When iterating on low-`r` search, use `lowr_diagnostic` as an extra side set
   rather than changing `submit_core` too early

## Notes

- This is `v2` of the local criterion, not a final truth.
- `v94` dropping online to `365.30` is the main reason this directory exists:
  broad local totals were still too easy to misread.
- If future online results disagree again, update these manifests before
  resuming algorithm-first iteration.
