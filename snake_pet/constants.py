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
TICK_MS = 33          # 帧间隔(约 30fps)
QUIET_STEP = 1.6      # 安静档步速(px/帧)
ACTIVE_STEP = 9.5     # 活跃档步速(px/帧)

# v4 的 DIRS 四方向格点移动与 SPIN_DIRS 8 方向打转已在 P1/P2 移除,
# 由连续角度转向(heading_angle + steer)与分层盘旋(CoilPlan)替代。

# ---- P1 360° 转向参数(供调参) ----
MAX_TURN_QUIET = 0.10        # 安静档每帧最大转角(rad)
MAX_TURN_ACTIVE = 0.18       # 活跃档每帧最大转角(rad)
WANDER_DRIFT_SIGMA = 0.03    # 闲逛每帧目标角高斯抖动(rad)
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

# ---- 经典绿系配色(v5-P3 作为默认主题) ----
C_BODY = ((155, 232, 159), (111, 217, 122), (85, 201, 107), (67, 186, 94))
C_HEAD = (166, 237, 169)
C_BELLY = (227, 251, 230)
C_TAIL = (201, 242, 195)
C_EYE = (255, 255, 255)
C_PUPIL = (51, 51, 51)
C_BLUSH = (255, 183, 197)
C_MOUTH = (60, 110, 71)

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

# ---- 默认配置(ver=2 为 v4 迁移链末端, v5-P6 再延伸到 5) ----
DEFAULT_CFG = {
    'no_eat': False,
    'no_spawn': True,
    'state': 'auto',
    'autostart': True,
    'ver': 2,
}
