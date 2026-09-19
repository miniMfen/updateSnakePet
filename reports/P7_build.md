# P7 构建与启动烟测报告（AC-F8-4，按 D-008 交付形态）

> 用户明确指示"不要把全部代码封装进一个 exe 文件里"——交付形态为**源码仓库 + 启动小蛇.bat**，
> PyInstaller 单文件打包豁免（STATUS·D-008）。本报告以等价烟测替代 exe 构建清单。

## 启动小蛇.bat 烟测（2026-09-19 实测）

| # | 检查项 | 结果 |
|---|---|---|
| 1 | 双击 bat → pythonw 进程出现 | ✓ 启动耗时 **0.7s**（≤5s 要求） |
| 2 | 单实例互斥：二次启动静默退出 | ✓ 二次启动后 pythonw 实例数仍为 1 |
| 3 | 宠物窗口创建 | ✓ 日志 `宠物窗口 hwnd=0x2a06f0` |
| 4 | 看门狗自愈 | ✓ 日志 `长时间被遮挡,主动重建窗口`(遮挡恢复自动重建) |
| 5 | 退出进程消失、无残留窗口 | ✓ taskkill 后 tasklist 无 pythonw |
| 6 | 配置/存档落盘 | ✓ 仓库根 snake_pet_config.json / pet_state.json（SNAKEPET_HOME 可重定向） |

> 修复记录:bat 初版以 UTF-8 保存导致中文注释在 GBK cmd 下乱码,已改用 GBK 编码 + CRLF 重写。

## 交付运行方式

- 双击 `启动小蛇.bat`（自动检测 Python/Pillow,首次自动装 Pillow）。
- 或命令行:`python run_pet.py` / `python -m snake_pet`。
- 开机自启动:菜单开关,注册表指向仓库根 `run_pet.py`。

## 日志轮转（AC-F8-3）

`RotatingFileHandler(maxBytes=5MB, backupCount=2)` —— snake_pet.log 超 5MB 自动轮转,最多 2 个备份。
