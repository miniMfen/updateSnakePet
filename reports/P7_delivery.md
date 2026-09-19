# P7 交付包核对报告（G7-3）

## 交付形态

按用户指示（STATUS·D-008）：**git 仓库本体即交付物**（源码 + 素材 + 文档 + 证据），
未打包单文件 exe；启动方式为 `启动小蛇.bat`。

## dist/delivery/ 内容核对

| 文件/目录 | 状态 |
|---|---|
| `启动小蛇.bat`(GBK 编码,双击启动) | ✓ |
| `run_pet.py` | ✓ |
| `README.md`(快速开始/交互表/目录结构) | ✓ |
| `使用说明.md`(安装/交互/菜单图解/养成机制/常见问题) | ✓ |
| `CHANGELOG.md`(v4→v5 全量变更 + 素材致谢) | ✓ |
| `素材致谢.md`(Fluent Emoji MIT / いらすと야 署名) | ✓ |
| `sprites/`(hats 7 顶 + hats.json + apple/cap 兼容位) | ✓ |
| 探针样张 3 张(游动/盘旋/菜单) | ✓ |

## 仓库结构核对（README 链接文件全部在位）

- snake_pet/ 源码包 ✓、tests/ ✓、reports/ 全阶段证据 ✓、sprites/ ✓、启动小蛇.bat ✓、run_pet.py ✓、README.md ✓、CHANGELOG.md ✓、使用说明.md ✓、.gitignore ✓。

## 版本与 git

- 版本:v5.0.0(snake_pet/__init__.py __version__)。
- 提交序列:P0→P1→P2→P3→P4→P5→P6→P7 每阶段一个里程碑提交。

## 用户人工清单（U01~U10）

已随交付发布(见 02_ACCEPTANCE §3),待用户日常使用后反馈;期间问题走 qa/BUGFIX_LOOP.md。
计分卡第 7 项按"待用户确认"记录,不阻塞代码交付。
