# P7 MUST 级 AC 逐条核对表（记分卡第 5 项）

> 每条 AC 的证据指向 reports/ 下的实际产物或代码位置。F7 裁剪见 STATUS·D-017。

## F1 360° 自由游动

| AC | 判定 | 证据 |
|---|---|---|
| F1-1 转向连续(角速度≤上限) | ✓ | T02 test_turn_continuity_t02(P1);MAX_TURN_QUIET/ACTIVE 常量 |
| F1-2 800px 外食物 30s 内吃到 | ✓ | T03 test_chase_converge_800px_t02(3 种子) |
| F1-3 不出界/避让/1s 脱困 | ✓ | T04 test_corner_escape_t04 + test_avoid_rects_never_entered |
| F1-4 节距≈SEG、内存受控 | ✓ | T01 test_segment_spacing_close_to_seg + soak path_max≤6000 |
| F1-5 v4 selftest 全过 | ✓ | 每阶段 `--selftest OK`(360° 版 Snake) |

## F2 分层盘旋

| AC | 判定 | 证据 |
|---|---|---|
| F2-1 三阶段完整、方向连续 | ✓ | T05 test_coil_geometry_t05(θ 连续性断言) |
| F2-2 圈距≥1.6×BODY_R、≥2 层 | ✓ | test_coil_plan_feasible_and_layered(公式独立复算)+探针 probe_05_盘旋 |
| F2-3 盘旋整体在 bounds 内 | ✓ | T06 test_coil_in_bounds_t06 |
| F2-4 可中断(食物/拎起) | ✓ | test_coil_interrupt_by_food / test_coil_interrupt_by_deviation |
| F2-5 结束状态干净 | ✓ | 同上(quit 后 coil/forced_angle 为 None) |
| F2-6 短蛇降级 | ✓ | test_coil_short_snake_degrades |
| F2-7 单测覆盖 | ✓ | tests/test_coil.py 7 例 |

## F3 蛇形象优化

| AC | 判定 | 证据 |
|---|---|---|
| F3-1 描边/眼高光/吐信/表情/眨眼 | ✓ | render._draw_head 部件化 + test_tongue_frame_draws + probe_18 |
| F3-2 锥形/外轮廓/腹带/背纹,盘旋不糊 | ✓ | _draw_snake 五层 + probe_05(多层圈清晰) |
| F3-3 主题≥3 套可切换,默认同 v4 色系 | ✓* | 5 套皮肤;默认=翡翠玉蛇(D-012 用户指令),经典绿保留可切换 |
| F3-4 性能≤2×基线且 FPS≥20 | ✓ | P3_soak:16.2ms vs 基线 34.4ms,FPS 27.71 |
| F3-5 探针人工确认"更精致" | ✓* | probe 图组已交用户(交付时确认,不阻塞) |

## F4 帽子系统

| AC | 判定 | 证据 |
|---|---|---|
| F4-1 ≥5 顶,贴图+兜底双通道 | ✓ | 7 顶;test_missing_png_falls_back / test_corrupt_png_falls_back |
| F4-2 随头旋转≤15° 偏差、缩放随阶段 | ✓ | probe_06~09 四朝向;帽位乘 _stage_render(P6) |
| F4-3 菜单切换即时+持久化+auto 语义 | ✓ | P4_menu.md + test_hat_config_roundtrip_and_invalid |
| F4-4 缺图/坏图兜底+告警不崩 | ✓ | test_missing_png_falls_back(caplog 断言 WARNING) |

## F5 互动增强

| AC | 判定 | 证据 |
|---|---|---|
| F5-1 投喂生效且受 MAX_FOODS 约束 | ✓ | test_feed_one_places_food |
| F5-2 抚摸判定准确、冷却、动画 | ✓ | test_petting_flow_t10 / test_petting_auto_complete |
| F5-3 拎起不撕裂、落位合法、掉落特效 | ✓ | test_drag_keeps_segment_spacing(修正 pos() 插值,D-013) |
| F5-4 与既有交互无冲突;睡中拎起唤醒 | ✓ | 冲突矩阵 7 项单测 + test_drag_wakes_sleeping_snake |

## F6 养成系统

| AC | 判定 | 证据 |
|---|---|---|
| F6-1 消化生效(≥1px/s,不低于基线) | ✓ | test_digest_t11_1 + soak 900s 消化日志 35 条 |
| F6-2 三阶段阈值与系数、2s 平滑 | ✓ | test_stage_t11_2 / test_stage_transition_smooth |
| F6-3 胖瘦生效并回落 | ✓ | test_fatness_t11_3 |
| F6-4 皮肤≥5 套、门槛、持久 | ✓ | test_skin_unlock_t11_4(门槛表见 D-015) |
| F6-5 成就≥8 个、一次性、UI 可见 | ✓ | test_achievements_t11_5 + 菜单成就行 |
| F6-6 存档闭环、坏档不崩 | ✓ | P6_persistence.md 实测 + test_state_roundtrip_and_corrupt |
| F6-7 v2/v3/v4 旧配置迁移 | ✓ | test_migration_from_ver1 / test_migration_from_v4_config |

## F8 工程与交付

| AC | 判定 | 证据 |
|---|---|---|
| F8-1 菜单扩容不溢出 | ✓ | probe_20(14 行网格布局,hatgrid 折行模式) |
| F8-2 CLI 三件套可用 | ✓ | reports/P0~P7 各 selftest/soak/probe 产物 |
| F8-3 日志轮转≤5MB、异常兜底非 0 退出 | ✓ | RotatingFileHandler(5MB×2);main() 异常 re-raise |
| F8-4 PyInstaller 单文件 exe | ⊘ | **按用户指示改为源码仓库+启动小蛇.bat**(D-008);bat 烟测见 P7_build.md |
| F8-5 交付包完整 | ✓ | dist/delivery/(使用说明/CHANGELOG/素材致谢)+仓库本体 |

**F7 喝水提醒/番茄钟/恶作剧:整体裁剪(D-017),SHOULD 级允许。**

> ✓* 标注项:主观确认部分待用户交付时勾选(AC-F3-3 默认色经用户指令修订、AC-F3-5 目测确认)。
