'''常量表 —— 与 00_BASELINE §12 逐一对齐(P0 重建, 默认值保持不变)'''
import math

APP_NAME = 'SnakePet'
AUTOSTART_NAME = 'SnakePet'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'

# ---- 蛇体几何 ----
SEG = 20              # 节距(px)
HEAD_R = 17           # 头半径
BODY_R = 10           # 身半径
EAT_RADIUS = 15       # 进食半径
GROW_PER_FOOD = 20    # 每食物增长像素
MAX_FOODS = 30        # 食物数上限
BODY_MIN = SEG * 2    # 体长下限(px)
BODY_MAX = SEG * 100  # 体长上限(px)
MARGIN = 26           # 活动边界内缩
MAX_PATH = 6000       # 轨迹点上限
PAD = 30              # 窗口外边距

# ---- 帧率与步速 ----
TICK_MS = 22          # 帧间隔(约 45fps 目标,v5.1 由 33 提升)
QUIET_STEP = 1.6      # 安静档步速(px/帧)
ACTIVE_STEP = 9.5     # 活跃档步速(px/帧)

# v4 的 DIRS 四方向格点移动与 SPIN_DIRS 8 方向打转已在 P1/P2 移除,
# 由连续角度转向(heading_angle + steer)与分层盘旋(CoilPlan)替代。

# ---- P1 360° 转向参数(供调参) ----
# 转弯半径 = 步速 / 每帧转角:v5.1.1 调低转角使弧线更大更圆滑(参考贪吃蛇网游的顺滑弯)
MAX_TURN_QUIET = 0.045       # 安静档每帧最大转角(rad,半径≈36px)
MAX_TURN_ACTIVE = 0.095      # 活跃档每帧最大转角(rad,半径≈100px)
MIN_TURN_DEADZONE = 0.06     # 最小转弯角度(rad,约 3.4°):低于它不转向,消除细碎抖弯
WANDER_DRIFT_SIGMA = 0.016   # 闲逛每帧目标角高斯抖动(rad,v5.1.1 调低更顺滑)
WANDER_BIAS_INTERVAL = (90, 220)  # 趋势角重置周期(帧)
WANDER_BIAS_RANGE = math.pi * 2 / 3  # 趋势角重置偏摆幅(±120°)
EDGE_INFLUENCE = 60          # 边界内推起始距离(px)
EDGE_PUSH_GAIN = 1.6         # 内推场增益(越贴边转得越急)
STALL_TIMEOUT = 60           # 追食卡死判定(帧)

# ---- P2 分层盘旋参数 ----
MAX_TURN_COIL = 0.25         # 盘旋档每帧最大转角(rad)
COIL_R0_RANGE = (60, 100)    # 盘旋外圈半径随机范围(px,约 80±20)
COIL_R_MIN_FACTOR = 2.2      # 最小圈半径 = 系数 × BODY_R(保证圈间有缝)
COIL_GAP_FACTOR = 1.9        # 圈距 = 系数 × BODY_R(≥1.6 即达标,留裕量)
COIL_OMEGA_RANGE = (2.0, 2.6)  # 角速度范围(rad/s)
COIL_MARGIN_FACTOR = 2.5     # 外接圆余量 = 系数 × BODY_R
COIL_DEVIATION_ABORT = 60    # 期望点偏差超过该值 → 快速盘出(px)
COIL_CARROT_LOOK = 6         # 胡萝卜前视帧数(头自身角度前方 ω×look 处)
COIL_ABORT_GRACE_FRAMES = 15 # 起步宽限帧数(对准切线前不判中断)
COIL_ABORT_GRACE_DIST = 150  # 起步宽限内的中断距离阈值(px)
COIL_DWELL_RANGE = (60, 150) # 盘踞时长(帧,约 2~5s)
COIL_OUT_RANGE = (40, 70)    # 盘出时长(帧)
COIL_MAX_SEGS_SMALL = 10     # 体长 ≤ 该节数 → 降级为小圈

# ---- 经典绿系配色(v4 原配色,保留为主题2) ----
C_BODY = ((155, 232, 159), (111, 217, 122), (85, 201, 107), (67, 186, 94))
C_HEAD = (166, 237, 169)
C_BELLY = (227, 251, 230)
C_TAIL = (201, 242, 195)
C_EYE = (255, 255, 255)
C_PUPIL = (51, 51, 51)
C_BLUSH = (255, 183, 197)
C_MOUTH = (60, 110, 71)

# ---- P3 主题表(≥3 套;字段见 reports/P3_style_analysis.md §3) ----
# ⚠ v5.2 刻意「名/色交叉」—— 用户 2026-09-20 指示:
#   诉求是「经典改为默认皮肤、翡翠改为需解锁皮肤」,但用户明确要求
#   「按下这两个按键后的颜色跟原来是一样的」。因此**只互换两者的 name,配色与顺序不动**:
#     索引 0(默认,门槛 0) 显示「经典绿」 → 实际渲染 jade 调色板
#     索引 1(需解锁,门槛 3) 显示「翡翠玉蛇」 → 实际渲染 v4 经典绿调色板
#   若日后要让名与色严格对齐,把下面两处的 name 值换回来即可(仅两行)。
# 主题1「翡翠玉蛇」:以微软 Fluent 3D 蛇(snake_fluent3d.png, MIT)量化取色为基准
SNAKE_THEMES = (
    {
        'id': 'jade', 'name': '经典绿',
        'body': ((96, 214, 150), (72, 196, 140), (58, 172, 122), (46, 148, 104)),
        'head': (104, 218, 156),
        'belly': (214, 244, 222),
        'tail': (120, 210, 150),
        'pattern': (190, 205, 70),
        'pattern_alt': (255, 232, 120),
        'outline': (38, 106, 82),
        'pupil': (45, 42, 40),
        'blush': (255, 170, 185),
        'mouth': (46, 96, 74),
        'tongue': (255, 96, 128),
    },
    {
        'id': 'classic', 'name': '翡翠玉蛇',
        'body': C_BODY,
        'head': C_HEAD,
        'belly': C_BELLY,
        'tail': C_TAIL,
        'pattern': (255, 255, 255),
        'pattern_alt': (255, 255, 255),
        'outline': (52, 118, 60),
        'pupil': C_PUPIL,
        'blush': C_BLUSH,
        'mouth': C_MOUTH,
        'tongue': (255, 120, 140),
    },
    {
        'id': 'peach', 'name': '蜜桃粉',
        'body': ((255, 205, 190), (250, 178, 170), (242, 152, 155), (228, 128, 145)),
        'head': (255, 210, 196),
        'belly': (255, 240, 232),
        'tail': (252, 196, 190),
        'pattern': (255, 170, 150),
        'pattern_alt': (255, 220, 200),
        'outline': (170, 90, 100),
        'pupil': (70, 48, 50),
        'blush': (255, 140, 150),
        'mouth': (150, 80, 90),
        'tongue': (235, 90, 110),
    },
    {
        'id': 'nightglow', 'name': '夜光',
        'body': ((70, 90, 120), (52, 72, 104), (40, 58, 90), (30, 44, 74)),
        'head': (78, 98, 128),
        'belly': (188, 214, 240),
        'tail': (62, 82, 112),
        'pattern': (120, 240, 200),
        'pattern_alt': (200, 255, 240),
        'outline': (18, 28, 48),
        'pupil': (20, 24, 34),
        'blush': (120, 150, 210),
        'mouth': (150, 180, 220),
        'tongue': (120, 200, 255),
    },
    {
        'id': 'clown', 'name': '小丑',
        'body': ((255, 170, 90), (248, 140, 70), (238, 110, 60), (220, 90, 52)),
        'head': (255, 176, 96),
        'belly': (255, 236, 210),
        'tail': (250, 158, 84),
        'pattern': (255, 255, 255),
        'pattern_alt': (60, 60, 66),
        'outline': (120, 62, 40),
        'pupil': (50, 42, 40),
        'blush': (255, 120, 110),
        'mouth': (140, 70, 50),
        'tongue': (240, 100, 110),
    },
)
THEME_IDS = tuple(t['id'] for t in SNAKE_THEMES)
THEME_NAMES = tuple(t['name'] for t in SNAKE_THEMES)
DEFAULT_THEME = 'jade'  # 用户指定以 snake_fluent3d 形象为默认(见 STATUS·D-012)

# ---- 食物配色 ----
C_FOOD = (255, 90, 95)
C_FOOD_SHADE = (230, 57, 70)
C_FOOD_HI = (255, 209, 211)
C_FOOD_STEM = (141, 110, 99)
C_FOOD_LEAF = (76, 175, 80)
C_FOOD_LEAF_VEIN = (46, 125, 50)

# ---- 特效 ----
C_EFFECT = (255, 209, 102)
FX_MAX = 80
FX_COLORS = ((255, 143, 177), (255, 209, 102), (127, 216, 255), (184, 242, 200), (201, 182, 255))

# ---- 夜帽手绘兜底色 ----
C_CAP = (139, 130, 226, 255)
C_CAP_DARK = (111, 102, 205, 255)
C_CAP_EDGE = C_CAP_DARK

# ---- 饱食度与心情 ----
SATIETY_MAX = 100
SATIETY_START = 70
SATIETY_GAIN = GROW_PER_FOOD
SATIETY_DECAY_PER_SEC = 0.1
MOOD_HAPPY = 60
MOOD_HUNGRY = 30

# ---- v5.2 睡觉流程(需求1:先盘旋 → 打呼噜 → 冷却) ----
# 旧行为:satiety 归零即刻就地入睡,睡 15~25s,无频率控制 → 用户反馈「跑着跑着直接打呼噜」
SLEEP_DUR_RANGE = (6.0, 12.0)           # 打呼噜时长(秒);从**盘旋结束**开始计时
SLEEP_COOLDOWN_RANGE = (300.0, 480.0)   # 唤醒后到下次允许入睡的最短冷却(秒,5~8min)
SLEEP_COIL_ATTEMPTS = 5                 # 入睡前最多尝试起盘次数,超限降级为直接入睡
SLEEP_COIL_RETRY_MS = 1200              # 起盘重试间隔(毫秒)

# ---- v5.2 避让:全屏透明覆盖层排除(AMD-01,见 run 的 scope/change_list.yaml) ----
# Windows 11 的 ShellHandwritingCanvas 等输入层用「全屏 + 置顶 + 分层」实现,
# 若计入避让会把整个工作区变成障碍 → make_coil_plan 恒返回 None。
# 实测(2026-09-20): 该窗口外扩 240px 后 = (-240,-240,1947,1307),幼蛇可用盘旋中心 0/2240 → 盘旋 100% 失效。
FULLSCREEN_OVERLAY_COVER_RATIO = 0.92   # 覆盖面积 / 虚拟屏面积 ≥ 此值 → 视为覆盖层,不避让
SHELL_OVERLAY_CLASSES = ('ShellHandwritingCanvas',)   # 已知 shell 覆盖层类名前缀

# ---- P3 身体绘制规格 ----
TAPER_TAIL = 0.55           # 身体锥形:尾端半径系数(头=1.0)
PATTERN_EVERY = 4           # 背部菱形斑间隔(采样节)
TONGUE_PERIOD = (240, 420)  # 吐信周期(帧,约 4~7s)
TONGUE_FRAMES = 8           # 吐信持续帧数

# ---- P6 养成数值表(与 tasks/P6_GROWTH.md §1 对应) ----
DIGEST_PX_PER_SEC = 2       # 消化速率:body_len 每秒回落像素
DIGEST_SATIETY_BELOW = 40   # 饱食度低于该值开始消化
DIGEST_FX_EVERY_SEC = 3     # 消化粒子间隔(s)
STAGE_TOTAL_EATEN = (20, 100)   # 幼蛇→成蛇→大蛇 的累计进食阈值
STAGE_COEFF = (1.0, 1.15, 1.3)  # 体型系数(作用于头/身半径与帽位)
STAGE_BASELINE_SEG = (5, 8, 12) # 各阶段体长基线(×SEG)
STAGE_TRANSITION_SEC = 2.0      # 阶段切换平滑过渡时长(s)
BODY_START_SEG = 8          # v5.1 初始体长(节,v4 为 5 节,用户反馈加长)
FATNESS_WINDOW_SEC = 600        # 胖瘦滚动窗口(10min)
FATNESS_PER_EAT = 0.05          # 每颗进食圆润增量
FATNESS_MAX = 0.25              # 圆润上限(系数 1.0~1.25)
SKIN_UNLOCK_EATEN = (0, 3, 8, 15, 25)   # 各皮肤解锁门槛(累计进食);v5.2 由 (0,10,30,60,100) 降低
PET_STATE_FILE = 'pet_state.json'
SAVE_PERIOD_SEC = 60            # 周期存档间隔(s)

# ---- P6 成就定义(id, 名称, 描述) ----
ACHIEVEMENTS = (
    ('first_feed', '初来乍到', '第一次撒食'),
    ('first_eat', '第一口', '第一次进食'),
    ('eater10', '小吃货', '累计吃 10 颗'),
    ('eater50', '干饭王', '累计吃 50 颗'),
    ('eater100', '传奇', '累计吃 100 颗'),
    ('seven_days', '七日之约', '累计运行跨 7 个自然日'),
    ('coil10', '转圈圈', '盘旋 10 次'),
    ('pet50', '摸头杀', '被抚摸 50 次'),
)

# ---- 默认配置(P6 迁移链末端 ver=5;v2/v3/v4 旧文件读入自动补齐) ----
DEFAULT_CFG = {
    'no_eat': False,
    'no_spawn': True,
    # v5.2 新增:关闭后饿着也不会缩回阶段基线(菜单「不再自然变短」)。默认 False = 保持原行为
    'no_digest': False,
    'state': 'auto',
    'autostart': True,
    'autosave': True,     # v5.1 记住小蛇(自动存档),菜单可关
    'theme': DEFAULT_THEME,
    'hat': 'auto',
    'ver': 5,
}

# ---- 渲染画质(v5.1.2) ----
SS_PIXEL_BUDGET = 1400000   # 单帧渲染像素预算初始值(自适应调节)
SS_BUDGET_MIN = 400000      # 预算下限(帧率优先)
SS_BUDGET_MAX = 2600000     # 预算上限(画质优先,机器快时自动提高)
SS_MAX = 2.0                # 超采样上限(小画布 2× 抗锯齿)
