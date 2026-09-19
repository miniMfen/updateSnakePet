'''互动状态机(P5) —— press/hold/drag 判定,纯逻辑、事件注入式、不碰 Win32。
状态:IDLE → PRESS_HEAD(按住头部) → PETTING(≥0.3s 且位移≤8px,冷却 2s)
                 └→ DRAG(位移>8px,拎起) → 松手 DROP
双击优先于抚摸/拎起(由调用方在 press 时先做双击判定)。'''
import math

HEAD_HIT_FACTOR = 1.5     # 头部命中区 = 系数 × HEAD_R
PET_HOLD_FRAMES_SEC = 0.3   # 抚摸最短持住时长(s)
PET_MOVE_TOL = 8.0        # 抚摸允许位移(px)
PET_DURATION = 1.2        # 抚摸自动完成时长(s)
PET_COOLDOWN = 2.0        # 抚摸冷却(s)
DRAG_THRESHOLD = 8.0      # 拎起位移阈值(px)
DRAG_MAX_STEP = 30.0      # 拎起单帧头位移上限(px,防瞬移拉裂)


class InteractSM:
    IDLE = 'idle'
    PRESS_HEAD = 'press_head'
    DRAG = 'drag'
    PETTING = 'petting'

    def __init__(self, bounds):
        self.bounds = bounds
        self.state = self.IDLE
        self.press_x = 0.0
        self.press_y = 0.0
        self.t0 = 0.0
        self.cursor = (0.0, 0.0)
        self.affinity = 0
        self.pet_cooldown_until = 0.0
        self.events = []          # 待主循环消费的动作事件

    # ---- 事件入口 ----
    def press(self, x, y, on_head, now):
        self.press_x, self.press_y = float(x), float(y)
        self.cursor = (float(x), float(y))
        self.t0 = now
        if on_head:
            self.state = self.PRESS_HEAD
        else:
            self.state = self.IDLE

    def move(self, x, y, now):
        self.cursor = (float(x), float(y))
        if self.state == self.PRESS_HEAD:
            d = math.hypot(x - self.press_x, y - self.press_y)
            if d > DRAG_THRESHOLD:
                self.state = self.DRAG
                self.events.append(('drag_start', x, y))
            elif now - self.t0 >= PET_HOLD_FRAMES_SEC:
                if now >= self.pet_cooldown_until:
                    self.state = self.PETTING
                    self.events.append(('pet_start', x, y))
        elif self.state == self.DRAG:
            self.events.append(('drag', x, y))

    def release(self, x, y, now):
        st = self.state
        self.state = self.IDLE
        if st == self.DRAG:
            self.events.append(('drop', x, y))
        elif st == self.PETTING:
            self._complete_petting(now)
        # PRESS_HEAD 短按(<0.3s 或冷却中) → 无动作(防误触)

    def tick(self, now):
        '''主循环每帧调用:静止持住进入抚摸;抚摸满 1.2s 自动完成'''
        if self.state == self.PRESS_HEAD:
            d = math.hypot(self.cursor[0] - self.press_x, self.cursor[1] - self.press_y)
            if now - self.t0 >= PET_HOLD_FRAMES_SEC and d <= PET_MOVE_TOL \
                    and now >= self.pet_cooldown_until:
                self.state = self.PETTING
                self.events.append(('pet_start', self.cursor[0], self.cursor[1]))
        if self.state == self.PETTING and now - self.t0 >= PET_HOLD_FRAMES_SEC + PET_DURATION:
            self._complete_petting(now)
            self.state = self.IDLE

    def _complete_petting(self, now):
        self.affinity += 1
        self.pet_cooldown_until = now + PET_COOLDOWN
        self.events.append(('pet_done', self.cursor[0], self.cursor[1]))

    def take_events(self):
        out = self.events
        self.events = []
        return out
