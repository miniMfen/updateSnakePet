'''常量表 —— 与 00_BASELINE §12 逐一对齐(P0 重建, 默认值保持不变)'''

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

# v4 四方向格点移动(v5-P1 将替换为连续角度; P0 原样保留)
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))

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

# v4 原地打转 8 方向表(v5-P2 分层盘旋整体替换, P0 保留兼容)
SPIN_DIRS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))

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
