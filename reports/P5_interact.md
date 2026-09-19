# P5 互动实录报告（G5-2）

## 冲突矩阵（实现 vs 任务书，逐条有单测，见 reports/P5_pytest.txt）

| 手势 | 语义 | 单测 |
|---|---|---|
| 桌面 press+release | 撒食（位置=press 点，即时） | test_conflict_matrix_desktop_spawn_unaffected |
| 蛇身 press+release（<0.3s 无位移） | 无动作（防误触） | test_short_press_no_action |
| 蛇身双击（0.45s 内二次按下） | hop+气泡，**优先于**抚摸/拎起 | test_conflict_matrix_double_click_priority |
| 蛇身右键 | 菜单 | test_conflict_matrix_right_click_menu |
| 头部 press+hold ≥0.3s（位移≤8px） | 抚摸（爱心+开心表情+affinity+1，冷却 2s） | test_petting_flow_t10 / test_petting_auto_complete |
| 头部 press+drag（>8px） | 拎起（头跟随光标、身体沿路径跟随、单帧限速 30px） | test_drag_flow_t10 / test_drag_keeps_segment_spacing |
| 睡觉中被拎起 | 立即唤醒（复用 `_wake`，satiety≥15） | test_drag_wakes_sleeping_snake |

## 三段实录（脚本化事件注入 + 真实渲染管线出帧，reports/P5_interact_frames/）

1. **抚摸爱心** `1_抚摸爱心.png`：press 头部持住 0.4s → PETTING → 完成：`affinity=1`、爱心粒子、气泡「好开心~」、摆尾。
2. **拎起弧线** `2_拎起弧线.png` / **放下** `3_放下尘土.png`：press 后 24 帧拖拽 → 头跟随光标、身体沿路径拉出弧线（节距保持）；松手尘土粒子 + body_scale 挤压回落。
3. **投喂追食** `4_投喂追食.png`：菜单「投喂一个苹果」→ 头前方 150~300px 生成食物 → 活跃档追食。

## soaK 事件注入（G5-3，reports/P5_soak.json）

600s 随机手势注入（pet/drag/click 混合）：`drags=32、pets=32、coils=3`，无异常，FPS 26.54，内存 +9.1MB。
