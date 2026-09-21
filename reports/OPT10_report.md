# OPT10 阶段报告 · 修复「在别的软件里右键也会弹出蛇菜单」

| 项 | 值 |
|---|---|
| run_id | `run-20260921T134130Z-bugrclick` |
| 标签 | `OPT10`（基线 `OPT10_BASE`） |
| 工程 | `D:\aiWorkCode\professionalWork\updateSnakePet` |
| 版本 | v5.2.1 → **v5.2.2** |
| 起点 commit | `f660b525602f713b52ba90d171e70c9b7cca870e`（master） |
| 结论 | **G1/G2/G3 PASS；G4 部分待人工确认；G5 待提交** |
| 整改次数 | 0 |

---

## 1. 用户报告与需求

> 「我在其它窗口的时候，比如我在文件打开 workbuddy 软件，这时候就是 workbuddy 的开发窗口了，
> 而且是全屏的，界面没有蛇，这时候如果我右键一个位置刚好是蛇在桌面上的位置，就会弹出菜单
> 而妨碍我工作。我想请你修复成我在非桌面界面的时候，点击右键即便刚好为蛇所在的位置，
> 也不会弹出菜单界面。」

**验收标准**：非桌面界面（该屏幕位置上最顶层不是桌面系）右键 → 不得弹菜单；
桌面上右键蛇身 → 必须照常弹。

---

## 2. 根因（真机实证）

`SnakePet._drain_events()` 处理**右键**时只做坐标命中判定：

```python
elif kind == 'R':
    hit = self._hit_snake(x - self.vx, y - self.vy)      # 命中半径 √1600 = 40px
    if not self.menu_open and hit:
        self._track_menu(x, y)
```

**完全没有校验那个屏幕位置上最顶层是哪个窗口**。而**同一函数**的左键分支却有归属校验
（`_is_desktop_at()`，"只有桌面才生成食物"）—— 一处明显的不对称（app.py:471 vs app.py:477-480）。
于是应用窗口盖住桌面时，用户在那个窗口里右键，只要坐标与蛇在桌面上的位置重合，菜单照样弹出。

**附带缺陷**：`_is_desktop_at()` 里还藏着 `if self._hit_snake(x, y): return True` 的**自命中短路** ——
把"坐标命中蛇身"当成"点在桌面上"，等于把归属校验整个绕过；且那里传的是**屏幕坐标**，
与 `seg_pos` 的**世界坐标**口径不一致（只有 `vx=vy=0` 时碰巧等价，实测本机 `vx=vy=0`，故为死代码）。

### 真机实测（决定判据怎么写）

`impl/diag_rclick.py` → `reports/BUG_RCLICK_check.json`：

| 观察 | 结果 |
|---|---|
| 全屏应用窗口盖住桌面时 `window_from_point(蛇头)` | 返回该应用窗口（实测类名 `Chrome_RenderWidgetHostHWND`）→ 桌面系 False |
| 桌面空白处同调用 | 返回桌面图标层 `SysListView32` → 桌面系 True |
| **把蛇窗口 `HWND_TOPMOST` 置顶后** `window_from_point(蛇头)` | **依然返回 `SysListView32`，从不返回蛇自己的 hwnd** |

> 第三条是关键：本机 `WindowFromPoint` **不参与 `UpdateLayeredWindow` 分层窗口的 alpha 命中测试**。
> ⇒ 判据**不能**写成"最顶层是不是自己"（本机恒为假），只能写成"最顶层是不是**桌面系**"。
> 代码里 `h == self._hwnd` 保留为其它环境的兜底分支。

---

## 3. 变更清单（与 `scope/change_list.yaml` 一致）

| 文件 | 变更 |
|---|---|
| `snake_pet/app.py` | 新增 `_point_is_desktop()`（归属判据）、`_should_open_menu_at()`（右键入口）；`_drain_events()` 的 `R`/`L` 分支加归属校验；`_is_desktop_at()` 去掉自命中短路并统一坐标口径 |
| `snake_pet/__init__.py` | `__version__` 5.2.1 → 5.2.2 |
| `tests/test_menu_rclick.py` | **新增** 18 例回归（既有断言零改动） |
| `CHANGELOG.md` / `README.md` / `使用说明.md` | 三处同步（交付协议） |

**未触碰**：`render.py`、`hats.py`、`constants.py`、`sprites.py`、`menu.py`、`platform_win.py`、`snake.py`、`config.py`、`growth.py`、`behavior.py`、`fx.py`、`interact.py` —— 一行未改。
**未触碰契约**：`constants.py` 的 10 个被断言数值、`DEFAULT_CFG`、`config.py` 迁移链、互斥名 —— 全部保持。

---

## 4. 五道闸门

| 闸门 | 结果 | 证据 |
|---|---|---|
| **G1 逻辑** | **PASS** | `OPT10_pytest.txt`（124 passed / 0 failed，基线 106）、`OPT10_selftest.txt`（OK） |
| **G2 性能** | **PASS** | 见 §4.1 |
| **G3 视觉** | **PASS** | 见 §4.2 |
| **G4 真机** | **PARTIAL** | 见 §4.3（阻塞人工） |
| **G5 交付** | 待提交 | 见 §5 |

### 4.1 G2 · 性能（3 样本比均值）

| 样本 | 修改前 `frame_ms_avg` | 修改后 `frame_ms_avg` |
|---|---|---|
| #1 | 16.636 | 17.477 |
| #2 | 15.779 | 17.465 |
| #3 | 16.330 | 17.723 |
| **均值** | **16.248 ms** | **17.555 ms** |

**差 +8.04%（阈值 10%）→ PASS**；`exceptions` 两侧均为 `[]`；`path_max=6000`；`fx_max=11`（≤80）。

**归因证据（为什么这 8% 不是本次改动引起的）**：
1. **零执行证明**：`OPT10_headless_pathcount.json` —— headless 180 秒主循环内
   `_point_is_desktop` / `_should_open_menu_at` / `_hit_snake` 调用次数均为 **0**
   （同期 `_drain_events` 被调用 4,936 次、队列事件总数 0）。改动只存在于鼠标事件分发路径上。
2. **基线代码当前环境对照**：把基线 commit 检出到 worktree 重跑同参 soak → 16.348 ms
   （`D:/tmp/snakepet-base-f660b52/reports/BASE_AB_soak.json`），与基线区间一致。
3. 首轮采集曾得到 18.9/18.4/19.4 ms 的偏高样本 —— 复核发现是**执行 AI 自己在采集期间并行跑了
   探针/worktree 等操作抢 CPU** 所致，已留存为 `OPT10_soak_polluted{1,2,3}.json` 并**静默重采**。
   （工作流 §R4 已警告本机噪声底达 45%；本次再次验证"采集必须静默"。）

### 4.2 G3 · 视觉

`render-probe` 20 场景齐全（与基线一致），`compare_probe` 结果：
`{'SIZE_CHANGED': 4, 'MATCHED': 16}`，3 条 alpha 覆盖率可疑项（游动 −19.0% / 追食 −20.8% /
吃食瞬间 −15.1%），判定提示 `REVIEW`。

**但这不是本次改动造成的** —— 用**基线代码**在 worktree 里做 A/A′（同一份代码跑两次）对照，
得到**逐项完全相同**的差异：同样 4 个 `SIZE_CHANGED`、同样 3 条可疑项、同样 19.0%/20.8%/15.1%；
修改后代码的 B/C 双跑同样出现 1.3~2.0% 差异（`OPT10_selfcheck_visualdiff`）。
⇒ 这是 `--render-probe` 的**固有非确定性**（新发现，已记入 `ISS-03`）。
「菜单」场景像素差异 **0.000%**，且渲染相关源码一行未改。

### 4.3 G4 · 真机（阻塞人工）

`impl/live_check.py`（非 headless，隔离 home，连续运行 120 秒）：

| 场景 | 结果 |
|---|---|
| **B：全屏应用窗口盖住蛇 + 右键其位置** | `menu_opened = **False**` ✅ **本次修复目标达成**（`top_class=Chrome_RenderWidgetHostHWND`） |
| A：桌面点 + 右键蛇 → 应弹菜单 | ⚠ **本环境无法复现**：屏幕被用户的全屏窗口完全占满，扫描 1550 个采样点**全部**是应用窗口，桌面点 0 个 |
| 真机连续运行 | 5,841 帧、`frame_ms_avg=14.211`、窗口句柄存活、窗口矩形正常 |
| 看门狗日志 | `长时间被遮挡→刷新画面` ×2（正常，因全屏窗口盖着）；1 条"失败"实为
`读取配置失败,使用默认值`（隔离 home 无配置文件，无副作用）；**0 次重建窗口** |
| 截图 | `OPT10_live_B_snake_covered.png`、`OPT10_live_D_after_run.png` |

> **待人工确认（唯一未闭合项）**：请兄弟**回到桌面**（把全屏窗口最小化）后在蛇身上右键，
> 确认菜单照常弹出、每行都能点。该场景已由单测
> `test_drain_events_opens_menu_on_desktop` / `test_menu_opens_on_desktop_over_snake` 覆盖，
> 但真机确认按工作流要求必须人工拍板。

---

## 5. 不变量核验（`OPT10_invariants.json`，机械判定 FAIL，逐条已查清）

| 不变量 | 机械判定 | 实情 | 结论 |
|---|---|---|---|
| INV-05 `reports/` 历史 | 修改 0 / 删除 0 | — | ✅ OK |
| INV-07 `tests/` | 变更 1 → 违规 | `changed: []`、`missing: []`、`added: ["tests/test_menu_rclick.py"]` —— **纯新增**，既有 106 例断言零改动 | ⚠ 需按"新增覆盖"处理（见下） |
| INV-02 用户存档 | `pet_state.json` 变更 → 违规 | 该文件最后写入时间 **22:08:57**，与 `snake_pet.log` 的 `存档已保存(quit)` 同刻 —— 是**用户自己的小蛇退出时写的**（内容 `total_eaten=49`、`body_len=1872`，属正常养成推进）。**反证**：此后我又运行了 4 个工具（180s soak、130s 真机、核验等），该文件 mtime **始终停在 22:08:57** | ❌ 误报 |

**关于 INV-07**：本次修复的防线就是这 18 例回归（工作流 G1 明确列出 `menu.py`/`app.py` 零单测覆盖）。
按工程先例（v5.2.1 同样新增 2 个测试文件 87→106 例）建议保留；若严格按字面规则需作废，请兄弟裁决。
核验器把"新增"与"修改"合并计为"变更"，建议工作流区分二者（已在 §7 提出）。

**本轮曾发生并已修复的一处自身违规**（`run_card.yaml` INC-01）：首次冻结基线时误用 `BASELINE`
作 tag，覆盖了 25 个已提交的 `reports/BASELINE_*` 文件；发现后立即 `git checkout -- reports/`
全量恢复，并改用独立 tag。

---

## 6. 交付物清单

**工程 `reports/`**
```
OPT10_pytest.txt  OPT10_selftest.txt  OPT10_soak.json  OPT10_S2_soak.json  OPT10_S3_soak.json
OPT10_probe/      OPT10_visualdiff/   OPT10_selfcheck_visualdiff/
OPT10_gate.json   OPT10_invariants.json  OPT10_headless_pathcount.json
OPT10_live.json   OPT10_live_B_snake_covered.png  OPT10_live_D_after_run.png
BUG_RCLICK_check.json                     （真机复现证据：修复前 True/True）
OPT10_BASE_* / OPT10_BASE_S2_* / OPT10_BASE_S3_*   （本轮基线，含 probe/soak/pytest）
OPT10_soak_polluted{1,2,3}.json           （首轮被并行负载污染的样本，留存备查）
```
**工作流 `runs/run-20260921T134130Z-bugrclick/`**：`run_card.yaml`、`intake/optimization-request.md`、
`scope/change_list.yaml`、`impl/{diag_rclick,count_paths,live_check}.py`、`handoff.md`

---

## 7. 顺带发现（本轮不修，如实记录）

| id | 内容 |
|---|---|
| ISS-03 | `--render-probe` 输出**并非逐像素确定**：同码双跑即出现 1.3~2.0% 差异与 4 个 `SIZE_CHANGED`。G3 的机读差异不能按"逐像素一致"判读，需要先测噪声底（与 G2 的 45% 噪声底同性质）。 |
| ISS-04 | `_hit_snake` 命中半径 40px 远大于蛇身半径（`BODY_R=10`）：蛇周围 30px 空白也算命中。属观感议题，需独立 run。 |
| ISS-05 | 工作流包 `03-scope/module-registry.yaml` 常量登记过时：写 `QUIET_STEP=1.6 / ACTIVE_STEP=9.5`，工程实际为 `1.16 / 6.91`（`app.selftest` 断言值）。会误导后续执行者对 INV-06 的判断。 |
| ISS-06 | `01-baseline/collect_baseline.py` 的 `--verify-invariants` 把 `tests/` 的"新增"与"修改"合并计为违规，建议区分 `added` / `changed` / `missing`。 |
