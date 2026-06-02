# Dataset Tiers

This directory defines the current local data criterion in `v3` layered form.

## `submit_core.txt`

Canonical primary ranking set.

Important:
- kept for backward compatibility with existing commands
- currently identical to `submit_backbone.txt`
- use this as the default submit / no-submit sorter

Current composition:
- `proxy_1..10`
- `bench_15`

2026-05-25 `v3` refactor:
- narrowed the old `submit_core`
- moved mixed-transfer families out of the primary ranker
- restored the main score to a cleaner proxy-like backbone

## `submit_backbone.txt`

Explicit name for the main backbone ranker.

Use this when you want the meaning to be obvious in scripts, notes, or compare
tables. It is intentionally the same as `submit_core.txt`.

## `submit_anchor.txt`

Secondary corroboration layer.

Current composition:
- `medium_25 / medium_32`
- `param_p32_hot / param_p32_r4_n40`

How to read it:
- this is **not** a standalone submit ranker
- if a version wins here but the backbone is flat, do not auto-promote it
- treat it as “still relevant locally, but historically easy to over-read”

Why it exists:
- these families were too mixed to stay inside the main ranker
- but they are not pure false positives either, so deleting them entirely would
  lose useful structure

## `contrast.txt`

Broad diagnostic layer.

Current composition:
- `bench_1 / bench_16`
- `proxy_11 / proxy_12`
- `medium_29 / medium_30 / medium_31`
- `param_r2_p32_hot / param_extreme_r2`

Use this set to explain *why* a branch moved, not to decide submit / no-submit
by itself.

## `prefport_veto.txt`

Strong verification layer.

Use this to block branches that only look better because they over-bias SA
proposals toward adjacent-phase already-used ports.

Current calibration target:
- rank `v232` above `v236 / v250 / v251`

Rule:
- do not submit a version that drops here unless the criterion itself is being
  intentionally revalidated

## `guardrail.txt`

Runtime / robustness layer.

Current composition:
- all `hard_*`
- all `ai_*`

Use this only to catch:
- timeout risk
- extreme runtime regressions
- severe robustness failures

Rule:
- a timeout seen under parallel load must be rerun serially before vetoing the
  branch

## `transfer_holdout.txt`

Near-neighbor low-confidence detector.

Current composition:
- low-transfer low-`r` family:
  `medium_31 / param_r2_p32_hot / param_extreme_r2`
- narrow parameter family:
  `param_r3_hot / param_n40_hot`
- low-`r` extensions:
  `lowr_1 / 4 / 7 / 8 / 10`

How to read it:
- this is **not** a submit ranker
- this is **not** the same as `submit_anchor`
- if a branch wins mostly here while the backbone stays flat, treat it as
  low-confidence for submission

Why it was not merged with `submit_anchor`:
- `submit_anchor` is a secondary **positive corroboration** layer
- `transfer_holdout` is a **concentration warning** layer
- mixing those two meanings would make near-neighbor reads harder, not easier

## `lowr_diagnostic.txt`

Temporary side manifest for `r<=3` research.

Use this when iterating on low-`r` search / repair ideas before deciding whether
any case family deserves promotion into `contrast`, `submit_anchor`, or
`transfer_holdout`.

## `candidate.txt`

Unvalidated exploration set.

Current role:
- hold newly generated structures before they have online evidence
- if a family rises here and also converts online, then decide whether it
  belongs in `submit_anchor`, `contrast`, or another layer

Current content:
- AI training style cases (`aitrain_*`)

## `online_proxy.txt`

线上分布推断集（candidate 层）。

依据：v318 本地+0.20 但线上仅+0.01，转化率分析表明当前 proxy 集代表性不足。
通过线上得分模式反推，生成贴近线上推断分布的 case。

Current composition (18 cases):
- `online_1..10`: 放大版 mixed（n=35-40, p=16-32, r=4, l=32-64）
- `online_11..13`: all-to-all 组通信拓扑
- `online_14..15`: 热点 leaf 拓扑（少数 leaf 承担大部分流量）
- `online_17..19`: 阶梯式负载（job 间流量差异大）

How to read it:
- 作为 candidate 层，不参与主排序
- 用于验证新算法改进是否对大规模 p=16-32 case 有效
- 如果某版本在此集上有显著收益且线上也转化，考虑晋升到 submit_anchor 或 contrast

## `aitrain.txt`

Mother set for the current AI-training candidate family.

## Commands

Score one tier:

```bash
python3 scripts/score_manifest.py ./solver datasets/submit_core.txt
python3 scripts/score_manifest.py ./solver datasets/submit_backbone.txt
python3 scripts/score_manifest.py ./solver datasets/submit_anchor.txt
python3 scripts/score_manifest.py ./solver datasets/contrast.txt
python3 scripts/score_manifest.py ./solver datasets/prefport_veto.txt
python3 scripts/score_manifest.py ./solver datasets/guardrail.txt
python3 scripts/score_manifest.py ./solver datasets/transfer_holdout.txt
```

## Suggested Workflow

1. Rank candidate versions on `submit_core` or `submit_backbone`
2. Check `submit_anchor` to see whether the gain has secondary corroboration
3. Read `contrast` to understand which broader families moved
4. Always check `prefport_veto` as a hard non-regression layer
5. Check `guardrail`; serially re-run any suspicious timeout before vetoing
6. For near-neighbor branches, inspect `transfer_holdout`
7. For low-`r` or AI-specific research, use `lowr_diagnostic` / `candidate`
   instead of polluting the main ranking too early

## Notes

- This is the current `v3` local criterion, not a final truth.
- `submit_core` is intentionally narrower than before.
- The split between `submit_anchor` and `transfer_holdout` is deliberate: one
  is a secondary positive signal, the other is a low-transfer warning signal.
