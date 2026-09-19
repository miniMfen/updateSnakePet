# P5 v4 交互回归清单报告（G5-4）

| # | v4 交互 | 回归方式 | 结果 |
|---|---|---|---|
| 1 | 桌面左键点击撒食（打开软件时点击不生成） | 单测 `test_conflict_matrix_desktop_spawn_unaffected`（状态机不拦截桌面 press）+ soak 600s 事件注入含桌面手势无异常 | 通过 |
| 2 | 蛇身右键弹菜单 | 单测 `test_conflict_matrix_right_click_menu` + 探针 probe_20 菜单渲染正常 | 通过 |
| 3 | 蛇身双击 | 单测 `test_conflict_matrix_double_click_priority`：双击 → hop+气泡，且优先于抚摸/拎起判定 | 通过 |
| 4 | 菜单各开关（不再吃/不再生成/自启/状态） | 单测 test_config 系列 + P0 parity 对照；自启开关走注册表成功才落盘（字节码仲裁语义） | 通过 |
| 5 | 单按蛇身 hop | **语义修订**（任务书冲突矩阵第 2 行）：单按改为无动作防误触，hop 移到双击；已在 P5_interact.md 冲突矩阵记录 | 按任务书执行 |
| 6 | 夜帽 auto（22:00–6:00） | P4 `test_resolve_hat_semantics`：夜间自动戴夜帽语义不变（现扩展为帽子衣柜的 auto 档） | 通过 |
| 7 | 沉底/点击穿透/单实例 | P0 parity 通过后无窗口层改动；soak 全程真实窗口运行无异常 | 通过 |

结论：v4 交互回归全部通过（唯一语义修订为任务书明确要求的单按防误触）。
