# P6 数值表核对报告（G6-1）

对照 `tasks/P6_GROWTH.md §1` 与实现（`constants.py` + `growth.py` + `app._growth_step`）：

| 项 | 任务书要求 | 实现 | 结果 |
|---|---|---|---|
| 消化速率 | satiety<40 时 ≥1px/s 回落 | `DIGEST_PX_PER_SEC=2`,satiety≥40 不消化 | ✓ |
| 消化下限 | 阶段基线 | `digest_step` floor=阶段基线 | ✓ |
| 消化粒子 | 每 3s 一粒淡绿气泡 | `DIGEST_FX_EVERY_SEC=3`,bfx 粒子+日志 | ✓ |
| 阶段阈值 | 幼<20 / 成≥20 / 大≥100 | `STAGE_TOTAL_EATEN=(20,100)` | ✓ |
| 阶段系数 | 1.0/1.15/1.3 作用于头/身/帽 | `STAGE_COEFF`,渲染头/身/帽统一乘 `_stage_render` | ✓ |
| 阶段过渡 | 2s 线性无跳变 | 每帧 `/15` 指数逼近(60帧后>95%),单测连续性 | ✓ |
| 阶段基线 | 5/8/12×SEG | `STAGE_BASELINE_SEG` | ✓ |
| 胖瘦 | 10min 窗口 n×0.05 上限 0.25 | `fatness_of` 滚动窗口,乘在身半径(头不乘) | ✓ |
| 皮肤 | 5 套门槛 0/10/30/60/100 | `SKIN_UNLOCK_EATEN`,菜单灰显+提示 | ✓ |
| 成就 | ≥8 个,一次性 | `ACHIEVEMENTS` 8 条,`Achievements.check` 幂等 | ✓ |
| 存档 | pet_state.json 全字段 ver:5 | `growth.py` default_state 全字段 | ✓ |
| 存档时机 | 退出+60s 周期+关键事件 | quit/periodic/achievement/stage/coil | ✓ |

# 皮肤与主题的关系（D-012 延续）

5 套皮肤 = P3 主题表扩容：翡翠玉蛇(0,默认)/经典绿(10)/蜜桃粉(30)/夜光(60)/小丑(100)。
任务书原定"经典绿门槛 0"因用户指定 fluent3d 形象为默认而调整：默认皮肤翡翠玉蛇门槛 0 保证新蛇可用，其余门槛数值保持 10/30/60/100 不变。

# 配置迁移报告（G6-4）

- `load_config`: `ver<5` → `no_spawn`(v1 语义保持) + `setdefault hat='auto'` + `setdefault theme='jade'` + `ver=5`。
- 单测：`test_migration_from_ver1`（v1→5,no_spawn 强制）、`test_migration_from_v4_config`（v4 字段无丢失）、`test_hat_config_roundtrip_and_invalid`（非法帽子回落）。
- 存档独立迁移：`load_pet_state` 字段缺省补齐（ver<5 不报错），损坏备份 `.bak-<ts>`。
- 结论：v2/v3/v4 旧 config 读入不丢字段，历史迁移语义保持（AC-F6-7）。
