# P0 常量表核对报告（G0-1）

对照 `00_BASELINE.md §12` 与 `snake_pet/constants.py`，逐一核对默认值：

| 常量 | BASELINE 要求 | constants.py | 结果 |
|---|---|---|---|
| SEG / HEAD_R / BODY_R / EAT_RADIUS | 20 / 17 / 10 / 15 | 20 / 17 / 10 / 15 | ✓ |
| GROW_PER_FOOD | 20 | 20 | ✓ |
| MAX_FOODS / BODY_MIN / BODY_MAX | 30 / 40 / 2000 | 30 / SEG*2=40 / SEG*100=2000 | ✓ |
| MARGIN / MAX_PATH / PAD | 26 / 6000 / 30 | 26 / 6000 / 30 | ✓ |
| TICK_MS | 33 | 33 | ✓ |
| QUIET_STEP / ACTIVE_STEP | 1.6 / 9.5 | 1.6 / 9.5 | ✓ |
| SATIETY_MAX / START / GAIN / DECAY | 100 / 70 / 20 / 0.1每秒 | 100 / 70 / GROW_PER_FOOD=20 / 0.1 | ✓ |
| MOOD_HAPPY / MOOD_HUNGRY | 60 / 30 | 60 / 30 | ✓ |
| C_BODY(4色绿渐变) | 绿系渐变 | (155,232,159)/(111,217,122)/(85,201,107)/(67,186,94) | ✓ |
| C_HEAD / C_BELLY / C_TAIL | 绿系 | (166,237,169)/(227,251,230)/(201,242,195) | ✓ |
| C_EYE / C_PUPIL / C_BLUSH / C_MOUTH | 白/墨/粉/绿 | (255,255,255)/(51,51,51)/(255,183,197)/(60,110,71) | ✓ |
| C_FOOD 系 | 红苹果色 | C_FOOD/(SHADE/HI/STEM/LEAF/LEAF_VEIN) 全套 | ✓ |
| FX_MAX / FX_COLORS | 80 / 5色 | 80 / 5 元组 | ✓ |
| C_CAP / C_CAP_DARK | 紫(139,130,226)/深紫 | (139,130,226,255)/(111,102,205,255) | ✓ |
| SPIN_DIRS | 8方向表 | 8 元组（P2 将替换） | ✓ |
| RUN_KEY / AUTOSTART_NAME | ...CurrentVersion\\Run / SnakePet | 一致（在 platform_win 引用） | ✓ |
| DEFAULT_CFG | no_eat/no_spawn/state/autostart/ver=2 | 与 v4 完全一致 | ✓ |

结论：常量表与 BASELINE §12 完全一致，无偏差。
