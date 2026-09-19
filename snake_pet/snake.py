'''蛇运动学 —— v5 360° 连续转向(P1)。
蛇头有朝向角 heading_angle(弧度, atan2 域), 每帧以受限角速度 steer 趋向目标方向;
身体仍沿路径按弧长采样, 天然支持任意角度。v4 的 DIRS 格点移动已废除。
本模块为纯运动学, 不依赖 Win32;确定性测试只需 random.seed。'''
import math
import random
from collections import deque

from .constants import (ACTIVE_STEP, BODY_R, COIL_ABORT_GRACE_DIST, COIL_ABORT_GRACE_FRAMES,
                        COIL_CARROT_LOOK, COIL_DEVIATION_ABORT, COIL_DWELL_RANGE,
                        COIL_GAP_FACTOR, COIL_MARGIN_FACTOR, COIL_MAX_SEGS_SMALL,
                        COIL_OMEGA_RANGE, COIL_OUT_RANGE, COIL_R0_RANGE, COIL_R_MIN_FACTOR,
                        EDGE_INFLUENCE, EDGE_PUSH_GAIN, EAT_RADIUS, GROW_PER_FOOD, MAX_PATH,
                        MAX_TURN_ACTIVE, MAX_TURN_COIL, MAX_TURN_QUIET, QUIET_STEP, SEG,
                        STALL_TIMEOUT, WANDER_BIAS_INTERVAL, WANDER_BIAS_RANGE,
                        WANDER_DRIFT_SIGMA)


def wrap_pi(a):
    '''把角度差归一化到 [-π, π]'''
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class CoilPlan:
    '''分层盘旋三阶段计划(P2):盘入(半径线性收敛)→盘踞(匀速)→盘出(反向展开)。
    每帧输出一个「期望头位置」交给转向器逼近,不做瞬移;支持快速盘出中断。'''

    def __init__(self, center, r0, r_min, omega_f, direction, t_in, dwell, t_out,
                 revs, small=False):
        self.cx, self.cy = center
        self.r0 = r0
        self.r_min = r_min
        self.omega_f = omega_f        # rad/帧
        self.dir = direction          # +1/-1 盘旋方向
        self.t_in = t_in              # 盘入帧数
        self.dwell = dwell            # 盘踞帧数
        self.t_out = t_out            # 盘出帧数
        self.revs = revs              # 盘入圈数(几何层)
        self.small = small            # 短蛇降级小圈标记
        self.t = 0
        self.fast = False             # 快速盘出(中断)标记
        self.theta0 = None            # 首帧按头位置校准,保证方向连续
        self._fast_start_t = None
        self._fast_r0 = None
        self._fast_t_out = None
        self.celebrated = False

    def radius_at(self, t):
        '''计划半径(纯几何,供测试与期望点计算)'''
        if self.fast and self._fast_start_t is not None and t >= self._fast_start_t:
            u = (t - self._fast_start_t) / self._fast_t_out
            return self._fast_r0 + (self.r0 - self._fast_r0) * min(1.0, u)
        if t < self.t_in:
            s = t / self.t_in
            return self.r_min + (self.r0 - self.r_min) * (1 - s)
        if t < self.t_in + self.dwell:
            return self.r_min
        u = (t - self.t_in - self.dwell) / self.t_out
        return self.r_min + (self.r0 - self.r_min) * min(1.0, u)

    def desired_point(self, hx, hy):
        '''期望头位置 (x, y, r, θ);θ 从首帧头位角连续起始'''
        if self.theta0 is None:
            self.theta0 = math.atan2(hy - self.cy, hx - self.cx)
        theta = self.theta0 + self.dir * self.omega_f * self.t
        r = self.radius_at(self.t)
        return (self.cx + math.cos(theta) * r, self.cy + math.sin(theta) * r, r, theta)

    def arc_speed(self):
        '''期望点的线速度(px/帧),作为盘旋期间的步速,保证头跟得上'''
        return self.omega_f * max(8.0, self.radius_at(self.t))

    def fast_unwind(self):
        '''快速盘出:从当前半径/角度无缝切入展开(时长缩短,不跳变)'''
        if self.fast:
            return
        self._fast_start_t = self.t
        self._fast_t_out = max(12, int(self.t_out * 0.4))
        self._fast_r0 = self.radius_at(self.t)   # fast 置位前快照当前半径
        self.fast = True

    @property
    def in_out_phase(self):
        return self.fast or self.t >= self.t_in

    @property
    def finished(self):
        if self.fast:
            return self._fast_start_t is not None and self.t >= self._fast_start_t + self._fast_t_out
        return self.t >= self.t_in + self.dwell + self.t_out


class Snake:
    def __init__(self, x0, y0, direction, bounds, body_len=SEG * 5):
        self.bounds = bounds
        self.body_len = float(body_len)
        # direction 兼容 v4 的方向元组(仅决定初始朝向角)
        if isinstance(direction, (int, float)):
            self.heading_angle = float(direction)
        else:
            (dx, dy) = direction
            self.heading_angle = math.atan2(dy, dx) if (dx or dy) else 0.0
        self.path = deque()
        self._pos_i = 0
        dist = 0
        ux = math.cos(self.heading_angle)
        uy = math.sin(self.heading_angle)
        for i in range(20, -1, -1):
            self.path.append((x0 - ux * i * 8, y0 - uy * i * 8, dist))
            dist += 8
        self.forced_angle = None      # 外部强制目标角(P2 盘旋复用);v4 forced_dir 的 360° 版
        self.coil = None              # CoilPlan(P2);非 None 时 move 走盘旋分支
        self._wander_target = self.heading_angle
        self._bias_timer = random.randint(*WANDER_BIAS_INTERVAL)
        self._avoid_side = 1          # 避让偏转侧记忆(防左右抖动)
        self._stall = 0               # 追食卡死计时
        self._chase_last_dist = 1e+18

    def head(self):
        return (self.path[-1][0], self.path[-1][1])

    def heading(self):
        '''头朝向单位向量(渲染接口与 v4 一致)'''
        return (math.cos(self.heading_angle), math.sin(self.heading_angle))

    def pos(self, behind):
        '''沿轨迹回溯 behind 距离处的坐标(带缓存索引加速,身体绘制用)。
        [P5-确认] v4 原实现在定位后于 [i-1,i] 段插值,目标实际落在 [i,i+1] 段,
        靠 1.6px 小步距掩盖误差;拎起引入 30px 大段后误差达 14px,已修正为
        在包含目标的 [i,i+1] 段上插值(对小步距行为不变)'''
        last = self.path[-1]
        target = last[2] - behind
        n = len(self.path)
        i = self._pos_i
        if i >= n:
            i = n - 1
        if self.path[i][2] <= target:
            while i + 1 < n and self.path[i + 1][2] <= target:
                i += 1
        else:
            while i > 0 and self.path[i][2] > target:
                i -= 1
        self._pos_i = i
        if i >= n - 1:
            q = self.path[n - 1]
            return (q[0], q[1])
        p = self.path[i]
        q = self.path[i + 1]
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
                dx, dy = 8.0, 0.0
            else:
                dy = (dy / L) * 8
                dx = (dx / L) * 8
            ny = p0[1] + dy
            nx = p0[0] + dx
            (x0, y0, x1, y1) = self.bounds
            self.path.appendleft((min(max(nx, x0), x1), min(max(ny, y0), y1), p0[2] - 8))

    # ---- 转向器(P2 盘旋复用) ----
    def steer(self, target_angle, max_turn):
        d = wrap_pi(target_angle - self.heading_angle)
        self.heading_angle += max(-max_turn, min(max_turn, d))

    # ---- 主步进 ----
    def move(self, step, active, foods, eat_enabled):
        (hx, hy) = self.head()
        if self.coil is not None:
            return self._move_coil(active, foods, eat_enabled)
        if self.forced_angle is not None:
            target = self.forced_angle
            self.forced_angle = None
            max_turn = math.pi / 4 + 1e-06   # 盘旋兼容层:每帧至多 45° 自转
        elif active and eat_enabled and foods and not getattr(self, 'ignore_food', False):
            target = self._chase(hx, hy, step, foods)
            max_turn = MAX_TURN_ACTIVE
        else:
            target = self._wander(hx, hy, step)
            max_turn = MAX_TURN_QUIET
        self.steer(target, max_turn)
        nx = hx + math.cos(self.heading_angle) * step
        ny = hy + math.sin(self.heading_angle) * step
        (cx, cy) = self._clamp(nx, ny)
        if (cx, cy) != (nx, ny):
            self._slide_along_edge(hx, hy, cx, cy, nx, ny)
        last = self.path[-1]
        nd = last[2] + math.hypot(cx - last[0], cy - last[1])
        self.path.append((cx, cy, nd))
        while len(self.path) > MAX_PATH:
            self.path.popleft()
        eaten = []
        if active and eat_enabled:
            for (fx, fy) in foods:
                if math.hypot(fx - nx, fy - ny) <= EAT_RADIUS:
                    eaten.append((fx, fy))
                    self.body_len += GROW_PER_FOOD
        return eaten

    # ---- 盘旋(P2):「导轨上的胡萝卜」追逐法 —— 胡萝卜固定在头自身角度前方
    # ω×look 处、半径取计划值:角度不滞后、半径自然收敛,复用限速转向 ----
    def _move_coil(self, active, foods, eat_enabled):
        plan = self.coil
        (hx, hy) = self.head()
        r_act = max(4.0, math.hypot(hx - plan.cx, hy - plan.cy))
        th_act = math.atan2(hy - plan.cy, hx - plan.cx)
        r_car = plan.radius_at(plan.t + COIL_CARROT_LOOK)
        ang = th_act + plan.dir * plan.omega_f * COIL_CARROT_LOOK
        tx = plan.cx + math.cos(ang) * r_car
        ty = plan.cy + math.sin(ang) * r_car
        dev = math.hypot(tx - hx, ty - hy)
        grace = plan.t < COIL_ABORT_GRACE_FRAMES
        if dev > (COIL_ABORT_GRACE_DIST if grace else COIL_DEVIATION_ABORT):
            plan.fast_unwind()   # 被拎起/碰壁等偏离过大 → 快速盘出
        step = min(ACTIVE_STEP, max(QUIET_STEP, plan.omega_f * r_act))
        if grace:
            step *= 0.45         # 起步对准切线:减速压低瞬态
        elif dev > 30:
            step *= 0.6
        self.steer(math.atan2(ty - hy, tx - hx), MAX_TURN_COIL)
        nx = hx + math.cos(self.heading_angle) * step
        ny = hy + math.sin(self.heading_angle) * step
        (cx, cy) = self._clamp(nx, ny)
        if (cx, cy) != (nx, ny):
            self._slide_along_edge(hx, hy, cx, cy, nx, ny)
            plan.fast_unwind()
        last = self.path[-1]
        nd = last[2] + math.hypot(cx - last[0], cy - last[1])
        self.path.append((cx, cy, nd))
        while len(self.path) > MAX_PATH:
            self.path.popleft()
        eaten = []
        if active and eat_enabled:
            for (fx, fy) in foods:
                if math.hypot(fx - nx, fy - ny) <= EAT_RADIUS:
                    eaten.append((fx, fy))
                    self.body_len += GROW_PER_FOOD
        plan.t += 1
        if plan.finished:
            self.coil = None
        return eaten

    # ---- 盘旋计划生成:中心选取 + 可行性 + 圈距约束 ----
    def make_coil_plan(self):
        '''按 P2 §2.1 选取中心并 clamp:优先头前方 r0 处,不可行时向两侧偏转找
        开阔中心;空间不足逐级缩 R0,仍不足返回 None(取消盘旋)。
        圈距 = (r0-r_min)/圈数 ≥ 1.6×BODY_R 由 COIL_GAP_FACTOR=1.9 保证;
        圈数同时受体长支撑(螺线弧长 ≈ 圈数×2π×平均半径)约束。'''
        (hx, hy) = self.head()
        (x0, y0, x1, y1) = self.bounds
        r_min = COIL_R_MIN_FACTOR * BODY_R
        gap = COIL_GAP_FACTOR * BODY_R
        omega_f = random.uniform(*COIL_OMEGA_RANGE) / 30.0
        direction = random.choice((-1, 1))
        small = self.body_len <= COIL_MAX_SEGS_SMALL * SEG
        if small:
            r0_candidates = (max(r_min + 10, 36),)
        else:
            r0_candidates = tuple(random.uniform(*COIL_R0_RANGE) * k for k in (1.0, 0.85, 0.7))
        for r0 in r0_candidates:
            r_need = r0 + COIL_MARGIN_FACTOR * BODY_R
            for dtheta in (0.0, math.pi / 4, -math.pi / 4, math.pi / 2, -math.pi / 2):
                ang = self.heading_angle + dtheta
                cx = hx + math.cos(ang) * r0
                cy = hy + math.sin(ang) * r0
                if not (x0 <= cx - r_need and cx + r_need <= x1
                        and y0 <= cy - r_need and cy + r_need <= y1):
                    continue
                blocked = False
                for (ax0, ay0, ax1, ay1) in getattr(self, 'avoid_rects', ()):
                    qx = min(max(cx, ax0), ax1)
                    qy = min(max(cy, ay0), ay1)
                    if (qx - cx) ** 2 + (qy - cy) ** 2 < r_need ** 2:
                        blocked = True
                        break
                if blocked:
                    continue
                if small:
                    revs = 1
                else:
                    revs_geo = max(2, int((r0 - r_min) / gap))
                    path_per_rev = 2 * math.pi * (r0 + r_min) / 2
                    revs_body = max(0, int(self.body_len / path_per_rev))
                    revs = min(revs_geo, revs_body)
                    if revs < 2:
                        continue  # 体长撑不起 ≥2 层 → 换更小 R0 或取消
                t_in = max(1, int(revs * 2 * math.pi / omega_f))
                dwell = COIL_DWELL_RANGE[0] if small else random.randint(*COIL_DWELL_RANGE)
                t_out = random.randint(*COIL_OUT_RANGE)
                return CoilPlan((cx, cy), r0, r_min, omega_f, direction, t_in, dwell,
                                t_out, revs, small=small)
        return None

    # ---- 追食 ----
    def _chase(self, hx, hy, step, foods):
        (fx, fy) = min(foods, key=lambda f: (f[0] - hx) ** 2 + (f[1] - hy) ** 2)
        dist = math.hypot(fx - hx, fy - hy)
        target = math.atan2(fy - hy, fx - hx)
        # 卡死计时:1s 内距离未缩短 → 随机大偏置一次,摆脱绕圈
        if dist < self._chase_last_dist - 0.5:
            self._stall = 0
        else:
            self._stall += 1
        self._chase_last_dist = dist
        if self._stall > STALL_TIMEOUT:
            self._stall = 0
            self._chase_last_dist = 1e+18
            return self.heading_angle + random.choice((-1, 1)) * random.uniform(1.0, 2.0)
        # 前方探测被挡 → 扇形采样首个合法方向(保持转向平滑,不直接设角)
        if not self._probe_ok(hx, hy, target, step):
            for off in (math.pi / 6, -math.pi / 6, math.pi / 3, -math.pi / 3,
                        math.pi / 2, -math.pi / 2, math.pi * 5 / 6, -math.pi * 5 / 6):
                a = target + off
                if self._probe_ok(hx, hy, a, step):
                    return a
        return target

    # ---- 闲逛 ----
    def _wander(self, hx, hy, step):
        self._bias_timer -= 1
        if self._bias_timer <= 0:
            self._bias_timer = random.randint(*WANDER_BIAS_INTERVAL)
            self._wander_target = self.heading_angle + random.uniform(-WANDER_BIAS_RANGE, WANDER_BIAS_RANGE)
        self._wander_target += random.gauss(0, WANDER_DRIFT_SIGMA)
        target = self._edge_push(hx, hy, self._wander_target)
        target = self._avoid_steer(hx, hy, step, target)
        return target

    def _edge_push(self, hx, hy, target):
        '''内推场:距任一边界 < EDGE_INFLUENCE 时,向内法向分量按距离线性加权混入目标方向'''
        (x0, y0, x1, y1) = self.bounds
        e = EDGE_INFLUENCE
        px = max(0.0, 1 - (hx - x0) / e) - max(0.0, 1 - (x1 - hx) / e)
        py = max(0.0, 1 - (hy - y0) / e) - max(0.0, 1 - (y1 - hy) / e)
        if abs(px) < 1e-9 and abs(py) < 1e-9:
            return target
        tvx = math.cos(target) + px * EDGE_PUSH_GAIN
        tvy = math.sin(target) + py * EDGE_PUSH_GAIN
        if abs(tvx) < 1e-9 and abs(tvy) < 1e-9:
            return target
        return math.atan2(tvy, tvx)

    def _avoid_steer(self, hx, hy, step, target):
        '''前方探测点落在避让矩形内 → 向可通行侧偏转(±45°起,记边防抖);
        找到合法方向后同步闲逛目标角,避免下一帧又转回障碍'''
        if self._probe_ok(hx, hy, target, step):
            return target
        for off in (math.pi / 6, math.pi / 4, math.pi / 3, math.pi / 2,
                    math.pi * 2 / 3, math.pi * 3 / 4):
            for sgn in (self._avoid_side, -self._avoid_side):
                a = target + sgn * off
                if self._probe_ok(hx, hy, a, step):
                    self._avoid_side = sgn
                    self._wander_target = a
                    return a
        return target

    def _lookahead(self, step):
        '''前方探测距离:步速 3 倍,安静档下限 60px 保证提前转弯'''
        return max(step * 3, 60)

    def _probe_ok(self, hx, hy, angle, step):
        '''双距离探测(60px 与 120px),对"墙"状障碍提前预警'''
        d0 = self._lookahead(step)
        for d in (d0, d0 * 2):
            if not self._ok(hx + math.cos(angle) * d, hy + math.sin(angle) * d):
                return False
        return True

    # ---- 边界与合法性 ----
    def _ok(self, x, y):
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

    def _slide_along_edge(self, hx, hy, cx, cy, nx, ny):
        '''clamp 生效时把朝向拉向切线方向,再叠加内推场分量——贴边滑行同时缓慢
        向内拐,防止正面顶墙抖动或沿墙爬不走'''
        (x0, y0, x1, y1) = self.bounds
        hit_x = cx != nx
        hit_y = cy != ny
        if hit_x and hit_y:
            tgt = math.atan2((y0 + y1) / 2 - hy, (x0 + x1) / 2 - hx)
        elif hit_x:
            tgt = math.pi / 2 if hy < (y0 + y1) / 2 else -math.pi / 2
            tgt = self._edge_push(hx, hy, tgt)
        else:
            tgt = 0.0 if hx < (x0 + x1) / 2 else math.pi
            tgt = self._edge_push(hx, hy, tgt)
        self.steer(tgt, MAX_TURN_ACTIVE * 2)
        self._wander_target = self.heading_angle
