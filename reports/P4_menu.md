# P4 菜单帽子行验证报告（G4-3）

## 布局（见 reports/P4_probe/probe_20_菜单.png）

- 「睡帽」行升级为「帽子」chips 网格：`自动 / 摘掉 / 夜帽 / 圣诞 / 皇冠 | 学士 / 礼帽 / 棒球 / 蝴蝶结`（9 枚折两行 5+4），布局扩容能力验证通过（P6/P7 菜单将复用 hatgrid 模式）。
- 渲染与命中表使用同一 `_hat_chip_box` 矩形计算，逐 chip 对齐；选中项绿色高亮。

## 行为

- 点击任一帽子 chip：`cfg['hat']` 立即更新 → `save_config` 持久化 → 菜单原地重绘（`_set_hat`）。
- 重启保持：配置文件写入 snake_pet_config.json 的 `hat` 字段；`load_config` 读取；非法值回落 `auto`（tests/test_hats.py::test_hat_config_roundtrip_and_invalid）。
- auto 语义与 v4 一致：夜间（22:00–6:00）戴夜帽、白天无帽（`resolve_hat`，tests/test_hats.py::test_resolve_hat_semantics）。

## 探针图

- 夜帽四朝向：probe_06~09（0°/90°/180°/270°，旋转跟随头朝向，目测偏差 ≤15°）。
- 帽子衣柜：probe_10~15（圣诞/皇冠/学士/礼帽/棒球/蝴蝶结，贴图 + 锚点贴合正常）。
