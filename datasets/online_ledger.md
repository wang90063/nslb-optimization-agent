# 线上提交台账（online ledger）

> **事实层**：每次线上提交记一行。这是 `calibrate-dataset` skill 的输入。
>
> **为什么需要它**：线上分是唯一**本地无法复算**的数据（来自线上评测机）。submit_core、candidate 总分、逐 case 分都能用 `submit/` 里归档的 solver 重跑得到——所以台账只需durably记下线上分，并把它和归档 solver 配对。校准时 `calibrate-dataset` 重跑这些 solver 重建逐 case 配对矩阵。

## Schema

每行一次线上提交：

| 列 | 含义 | 来源 |
|----|------|------|
| 版本 | vN | 提交时 |
| 日期 | MM-DD | 提交时 |
| 线上分 | 线上评测机总分 | **线上**（不可复算，必须记） |
| 线上Δ | 相对上一次提交的线上分变化 | 算出 |
| 思路 | wiki idea slug（外键） | 提交时 |
| solver | `submit/` 里的归档源文件名 | 提交时（calibrate 重跑用） |
| submit_core | 提交当时的 submit_core 总分（便捷快照，可复算） | 提交时，可空 |
| candidate总 | 提交当时的 candidate 总分（便捷快照，可复算） | 提交时，可空 |

**填写规则**：线上分、线上Δ、solver 指针是必填（校准的命脉）；submit_core / candidate总 是便捷快照，缺了不致命（calibrate 会重跑 solver 重建）。

## 台账

| 版本 | 日期 | 线上分 | 线上Δ | 思路 | solver | submit_core | candidate总 |
|------|------|-------|------|------|--------|-------------|-------------|
| v1 | 05-16 | 276 | — | | Solution_20260516_v1_roundrobin.cpp | | |
| v2 | 05-16 | 326 | +50 | | Solution_20260516_v2_greedy.cpp | | |
| v8 | 05-17 | 347 | +21 | per-flow-beats-per-card | Solution_20260517_v8_perflow.cpp | | |
| v18 | 05-18 | 352 | +5 | global-penalty-matters | Solution_20260518_v18_maxglobal.cpp | | |
| v22 | 05-18 | 355 | +3 | | Solution_20260518_v22_bottleneck_swap.cpp | | |
| v33 | 05-18 | 356 | +1 | | Solution_20260518_v33_allornone_swap.cpp | | |
| v43 | 05-18 | 359 | +3 | ensemble-3-strategies | Solution_20260518_v43_ensemble.cpp | | |
| v47 | 05-19 | 362.8 | +3.8 | | Solution_20260519_v47_maxmultir.cpp | | |
| v49 | 05-19 | 362.84 | +0.04 | | Solution_20260519_v49_ftrl.cpp | | |
| v51 | 05-19 | 362.89 | +0.05 | | Solution_20260519_v51_penalty.cpp | | |
| v56 | 05-19 | 362.89 | 0 | | Solution_20260519_v56_hugejob.cpp | | |
| v62 | 05-19 | 366.25 | +3.36 | better-metrics-lexico | Solution_20260519_v62_proxy_tiebreak.cpp | | |
| v77 | 05-20 | 366.25 | 0 | | Solution_20260520_v77_localftrl.cpp | | |
| v87 | 05-20 | 366.25 | 0 | | Solution_20260520_v87_hardcap_futuretie_p16.cpp | | |
| v93 | 05-20 | 365.60 | -0.65 | | Solution_20260520_v93_s11e_eqrank.cpp | | |
| v94 | 05-20 | 365.30 | -0.30 | | Solution_20260520_v94_s6e1_s11e_eqrank.cpp | | |
| v95 | 05-20 | 366.24 | +0.94 | | Solution_20260520_v95_jm_repair.cpp | | |
| v99 | 05-20 | 366.24 | 0 | | Solution_20260520_v99_deep_repair.cpp | | |
| v122 | 05-21 | 367.1 | +0.86 | score-aware-pc-chain | Solution_20260521_v122_better_port_consistency.cpp | | |
| v126 | 05-21 | 367.8 | +0.7 | score-aware-pc-chain | Solution_20260521_v126_neutral_swap.cpp | | |
| v129 | 05-21 | 368.04 | +0.24 | score-aware-pc-chain | Solution_20260521_v129_relaxed_swap.cpp | | |
| v138 | 05-21 | 369.12 | +1.08 | score-aware-pc-chain | Solution_20260521_v138_pc_scoreaware_globaltie.cpp | | |
| v151 | 05-21 | 369.13 | +0.01 | score-aware-pc-chain | Solution_20260521_v151_pc_work80k_fl5k.cpp | | |
| v163 | 05-21 | 369.21 | +0.08 | score-aware-pc-chain | Solution_20260521_v163_pc_alternating_refinegate.cpp | | |
| v181 | 05-22 | 369.21 | 0 | low-r-makeroom-consistency | Solution_20260522_v181_lowr_makeroom.cpp | | |
| v199 | 05-23 | 369.36 | +0.15 | | Solution_20260522_v199_perf_gate.cpp | | |
| v214 | 05-23 | 369.366 | +0.006 | | Solution_20260523_v214_r4_makeroom_top2.cpp | | |
| v230 | 05-24 | 369.43 | +0.064 | | Solution_20260524_v230_cbttskc_reduce.cpp | | |
| v232 | 05-24 | 369.65 | +0.22 | sa-effective-v232 | Solution_20260524_v232_sa_budget.cpp | | |
| v236 | 05-24 | 369.52 | -0.13 | sa-proposal-bias | Solution_20260524_v236_sa_prefport.cpp | | |
| v250 | 05-25 | 369.56 | +0.04 | sa-proposal-bias | Solution_20260524_v250_sa_prefport_single.cpp | | |
| v251 | 05-25 | 369.54 | -0.02 | sa-proposal-bias | Solution_20260524_v251_sa_prefport_vote.cpp | | |
| v255 | 05-25 | 369.649 | +0.109 | | Solution_20260525_v255_makeroom_futuretie_r3plus.cpp | | |
| v267 | 05-26 | 369.709 | +0.06 | | Solution_20260526_v267_post_sa_cb_recovery.cpp | | |
| v292 | 05-26 | 369.73 | +0.021 | focused-sa | Solution_20260526_v292_sa_3pass_focused.cpp | | |
| v305 | 05-26 | 369.55 | -0.18 | ct-direction | Solution_20260526_v305_post_sa_ct.cpp | | |
| v318 | 05-27 | 369.74 | +0.19 | sa-swap-2opt | Solution_20260527_v318_sa_swap.cpp | | |
| v361 | 05-28 | 369.76 | +0.02 | cross-dest-top3-mixed | Solution_20260528_v361_src_price.cpp | | |
| v369 | 05-28 | 369.86 | +0.10 | cross-dest-top3-mixed | Solution_20260528_v369_crossdest_price_mix.cpp | | |
| v381 | 05-29 | 369.35 | -0.51 | portfolio-diversity-matters | Solution_20260529_v381_time_budget.cpp | | |
| v404 | 05-30 | 369.85 | +0.50 | | Solution_20260530_v404_gp_cb_cold.cpp | | |
| v430 | 05-30 | 369.89 | +0.04 | time-tight-threshold-relax | Solution_20260530_v430_timetight_relax70.cpp | | |
| v436 | 05-30 | 369.73 | -0.16 | ct-propagation | Solution_20260530_v436_ct_propagate.cpp | | |
| v454 | 05-31 | 370.15 | +0.42 | actual-global-out | Solution_20260531_v454_actual_global_out.cpp | 902.03 | 455.54 |

## 归档完整性

全部 41 个线上提交版本的 solver 均已存入 `submit/`，calibrate 可重跑任一版本重建逐 case 配对。今后每次提交务必先归档 solver 再继续（见 `algorithm-iterate` 记录步），保持此完整性。

## sync 水位

- 最后回填：v454（2026-05-31），从 SCORES.md 排行榜回填
- 上次校准：2026-05-31（手动，6 升 core / 4 移 contrast / 8 留，见 logs/2026-05-31.md）
- 上次校准后的新提交数：0（v454 即校准当轮基线）
