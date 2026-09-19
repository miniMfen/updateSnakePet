# P6 存档闭环实测报告（G6-3）

环境：`SNAKEPET_HOME=reports/P6_persistence_home`（隔离目录）。

## 步骤与数据

1. **第一次会话**：全新启动（无存档）→ 配置皮肤 peach → 主动进食增长 → 解锁成就 coil10 → 退出（触发 quit 存档）。
   - 退出前：`pos=(909,808) body_len=100 satiety=70.0 skin=peach hat=auto ach=['coil10']`
2. **第二次会话**：重启（读档）。
   - 重启后：`pos=(909,808) body_len=100 satiety=70.0 skin=peach hat=auto ach=['coil10']`
   - **闭环还原：True**（位置/体长/饱食/皮肤/帽子/成就全部还原）

截图：`reports/P6_probe/persistence_before.png` / `persistence_after.png`（渲染帧前后对比，皮肤为蜜桃粉）。

## 容错验证

- 坏 JSON 存档 → 自动备份 `pet_state.json.bak-<ts>` 并新建默认档（tests/test_growth.py::test_state_roundtrip_and_corrupt）。
- 首次启动（无存档文件）→ 返回 None，不覆盖用户当前配置选择（皮肤/帽子以 config 为准）。

## 周期保存

- 60s 周期（时钟注入单测 test_periodic_save_clock）+ 退出保存 + 成就解锁/阶段切换/盘旋开始即时保存；soak 900s 中以日志 `存档已保存(periodic)` 观测。
