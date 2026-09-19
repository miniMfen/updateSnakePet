'''蛇运动学 —— v4 语义原样重建(P1 将把四方向 DIRS 改造为 360° 连续转向)。
数据模型: path = deque[(x, y, arc_len)],头在尾部追加;身体任意弧长位置由
pos(behind) 沿路径插值采样;移动是四方向格点式(每帧沿一个方向走 step 像素)。'''
import math
import random
from collections import deque

from .constants import (DIRS, EAT_RADIUS, GROW_PER_FOOD, MAX_PATH, SEG)


class Snake:
    def __init__(self, x0, y0, direction, bounds, body_len=SEG * 5):
        self.bounds = bounds
        self.body_len = float(body_len)
        self.head_dir = direction
        self.dir_timer = random.randint(60, 150)
        (dx, dy) = direction
        self.path = deque()
        self._pos_i = 0
        dist = 0
        for i in range(20, -1, -1):
            self.path.append((x0 - dx * i * 8, y0 - dy * i * 8, dist))
            dist += 8
        self.forced_dir = None

    def head(self):
        return (self.path[-1][0], self.path[-1][1])

    def heading(self):
        if len(self.path) >= 2:
            a = self.path[-1]
            b = self.path[-2]
            dy = a[1] - b[1]
            dx = a[0] - b[0]
            L = math.hypot(dx, dy)
            if L > 1e-06:
                return (dx / L, dy / L)
            return self.head_dir
        return self.head_dir

    def pos(self, behind):
        '''沿轨迹回溯 behind 距离处的坐标(带缓存索引加速,身体绘制用)'''
        last = self.path[-1]
        target = last[2] - behind
        i = self._pos_i
        if i >= len(self.path):
            i = len(self.path) - 1
        if self.path[i][2] > target:
            while i > 0 and self.path[i][2] > target:
                i -= 1
        else:
            i = len(self.path) - 1
            while i > 0 and self.path[i][2] > target:
                i -= 1
        self._pos_i = i
        q = self.path[i]
        if i == 0:
            return (q[0], q[1])
        p = self.path[i - 1]
        span = q[2] - p[2]
        t = (target - p[2]) / span if span > 1e-09 else 0
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)

    def ensure_path_len(self, need):
        '''确保移动轨迹总长 >= need(菜单里加长身体时,尾部有足够的轨迹可延伸)'''
        while self.path[-1][2] - self.path[0][2] < need:
            p0 = self.path[0]
            p1 = self.path[1]
            dy = p0[1] - p1[1]
            dx = p0[0] - p1[0]
            L = math.hypot(dx, dy)
            if L < 1e-06:
                (dx, dy) = (8, 0)
            else:
                dy = (dy / L) * 8
                dx = (dx / L) * 8
            ny = p0[1] + dy
            nx = p0[0] + dx
            (x0, y0, x1, y1) = self.bounds
            self.path.appendleft((min(max(nx, x0), x1), min(max(ny, y0), y1), p0[2] - 8))

    def move(self, step, active, foods, eat_enabled):
        (hx, hy) = self.head()
        if self.forced_dir is not None:
            d = self.forced_dir
            self.forced_dir = None
            if not self._ok(hx + d[0] * step, hy + d[1] * step):
                d = self._wander(hx, hy, step)
        elif active and eat_enabled and foods and not getattr(self, 'ignore_food', False):
            d = self._chase(hx, hy, step, foods)
        else:
            d = self._wander(hx, hy, step)
        self.head_dir = d
        (nx, ny) = self._clamp(hx + d[0] * step, hy + d[1] * step)
        last = self.path[-1]
        nd = last[2] + math.hypot(nx - last[0], ny - last[1])
        self.path.append((nx, ny, nd))
        while len(self.path) > MAX_PATH:
            self.path.popleft()
        eaten = []
        if active and eat_enabled:
            for (fx, fy) in foods:
                if math.hypot(fx - nx, fy - ny) <= EAT_RADIUS:
                    eaten.append((fx, fy))
                    self.body_len += GROW_PER_FOOD
        return eaten

    def _chase(self, hx, hy, step, foods):
        # [P0-确认] 依据 snake_pet_dis.txt `_chase`: score 最小者胜(同向小幅加分),禁 180° 反向
        (cx, cy) = self.head_dir
        (fx, fy) = min(foods, key=lambda f: (f[0] - hx) ** 2 + (f[1] - hy) ** 2)
        (best, best_score) = (None, None)
        for d in DIRS:
            if d[0] + cx == 0 and d[1] + cy == 0:
                continue
            ny = hy + d[1] * step
            nx = hx + d[0] * step
            if not self._ok(nx, ny):
                continue
            score = abs(fx - nx) + abs(fy - ny)
            if d == (cx, cy):
                score -= step * 0.6
            if best is not None and score >= best_score:
                continue
            best_score = score
            best = d
        if best:
            return best
        for d in DIRS:
            if not self._ok(hx + d[0] * step, hy + d[1] * step):
                continue
            return d
        return (-cx, -cy)

    def _wander(self, hx, hy, step):
        self.dir_timer -= 1
        (cx, cy) = self.head_dir
        if self.dir_timer <= 0:
            self.dir_timer = random.randint(80, 200)
            opts = [d for d in DIRS if not (d[0] + cx == 0 and d[1] + cy == 0)]
            random.shuffle(opts)
            for d in opts:
                if self._ok(hx + d[0] * 20, hy + d[1] * 20):
                    return d
        if not self._ok(hx + cx * step, hy + cy * step):
            opts = [d for d in DIRS
                    if not (d[0] + cx == 0 and d[1] + cy == 0) and self._ok(hx + d[0] * step, hy + d[1] * step)]
            if opts:
                return random.choice(opts)
            for d in DIRS:
                if self._ok(hx + d[0] * step, hy + d[1] * step):
                    return d
            return (-cx, -cy)
        return (cx, cy)

    def _ok(self, x, y):
        # [P0-确认] 依据修复版 + 字节码:bounds + avoid_rects 完整判定
        (x0, y0, x1, y1) = self.bounds
        if not x0 <= x <= x1:
            return False
        if not y0 <= y <= y1:
            return False
        for (ax0, ay0, ax1, ay1) in getattr(self, 'avoid_rects', ()):
            if ax0 <= x <= ax1 and ay0 <= y <= ay1:
                return False
        return True

    def _clamp(self, x, y):
        (x0, y0, x1, y1) = self.bounds
        return (min(max(x, x0), x1), min(max(y, y0), y1))
