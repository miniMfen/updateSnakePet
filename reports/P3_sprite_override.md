# P3 snake_head.png 覆盖机制回归报告（G3-4）

- 机制：`sprites/snake_head.png`（朝右蛇头贴图）存在时，`_draw_head` 整头替换为按 heading 旋转后的贴图（`_paste_head_sprite`，LANCZOS 缩放至 2.6×头径，BICUBIC 旋转）；看门狗监测色改用贴图主色。无贴图时使用内置部件化绘制，互不影响。
- 回归验证：`tests/test_render.py::test_head_sprite_override` ——
  1. 放入纯红色块贴图 → 渲染输出出现 >20 个红色像素（贴图生效）；
  2. 删除贴图 → 渲染输出与覆盖前逐字节一致（内置头完整恢复）。
- 结论：覆盖机制回归通过。验证用贴图已按任务书要求移除，交付包不含该文件。
