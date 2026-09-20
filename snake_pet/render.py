'''整帧 PIL 绘制 —— 蛇头/身体/食物/夜帽/文字气泡/菜单面板(v4 画法)。
纯 PIL,不碰任何 Win32 句柄;推送由 app 层完成。
作为 mixin 挂到 SnakePet 上,保持 v4 方法名与调用链不变。'''
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

from .constants import (BODY_R, C_BLUSH, C_CAP, C_CAP_EDGE, C_EFFECT, C_EYE, C_FOOD,
                        C_FOOD_HI, C_FOOD_LEAF, C_FOOD_LEAF_VEIN, C_FOOD_SHADE,
                        C_FOOD_STEM, C_MOUTH, C_PUPIL, DEFAULT_THEME, HEAD_R, PAD, SEG,
                        PATTERN_EVERY, SS_MAX, SNAKE_THEMES, TAPER_TAIL, TONGUE_FRAMES)
from .hats import HatRenderer, hat_anchor_pos, resolve_hat


class RenderMixin:
    # ---- 整帧组装 ----
    def _render_frame(self):
        '''把「蛇+食物+特效+气泡」画成整幅 RGBA,返回 (img, wx, wy);无可画内容返回 None'''
        snake = self.snake
        n = min(max(1, int(snake.body_len // SEG)), 100)
        segs = [snake.head()]
        for i in range(1, n):
            segs.append(snake.pos(i * SEG + 4))
        if self.hop > 0:
            hop_px = int(math.sin(math.pi * (8 - self.hop) / 8) * 7)
            segs = [(sx, sy - hop_px) for (sx, sy) in segs]
        self.seg_pos = list(segs)

        self._blink_timer -= 1
        if self._blink_timer <= 0:
            self._blink = 3
            self._blink_timer = random.randint(90, 210)
        blinking = self._blink > 0
        if blinking:
            self._blink -= 1

        pts = [(s[0], s[1]) for s in segs] \
            + [(f['x'], f['y']) for f in self.foods] \
            + [(e['x'], e['y']) for e in self.effects] \
            + [(fx['x'] + fx.get('vx', 0.0) * fx.get('max', 30),
                fx['y'] + fx.get('vy', 0.0) * fx.get('max', 30)) for fx in self.fx]
        self._current_hat_id = resolve_hat(self.cfg.get('hat', 'auto'), self._is_night())
        if self._current_hat_id is not None:
            (hx, hy) = (segs[0][0], segs[0][1])
            cw = HEAD_R * 2.6
            pts.append((hx - cw / 2, hy - HEAD_R * 1.2 - cw))
            pts.append((hx + cw / 2, hy - HEAD_R * 0.5))
        tail_d = snake.path[-1][2] - snake.body_len - 4
        for p in snake.path:
            if p[2] >= tail_d:
                pts.append((p[0], p[1]))
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        wx = int(min(xs) - PAD)
        wy = int(min(ys) - PAD)
        w = int(max(xs) - min(xs) + PAD * 2 + 2)
        h = int(max(ys) - min(ys) + PAD * 2 + 2)
        area = w * h
        # v5.1.2 自适应像素预算:预算随实测帧时间自动升降,
        # 小画布高倍抗锯齿(去马赛克),机器负载大时自动降档保帧率
        ss = min(SS_MAX, max(1.0, (self._ss_budget / max(1, area)) ** 0.5))
        img = Image.new('RGBA', (int(w * ss), int(h * ss)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        def L(px, py):
            return ((px - wx) * ss, (py - wy) * ss)

        for e in self.effects:
            (x, y) = L(e['x'], e['y'])
            r = (7 + e['t'] * 2.2) * ss
            d.ellipse([x - r, y - r, x + r, y + r], outline=C_EFFECT + (255,),
                      width=max(2, int(3 * ss)))
        for f in self.foods:
            self._draw_apple(img, d, *L(f['x'], f['y']), ss)
        tilt_deg = 0
        if self.tilt > 0:
            tilt_deg = int(14 * math.sin(math.pi * (12 - self.tilt) / 12))
        self._draw_snake(d, snake, ss, wx, wy)
        self._draw_head(img, d, *L(segs[0][0], segs[0][1]), ss, snake.heading(),
                        blinking, self._mood(), tilt_deg)
        for fx in self.fx:
            (x, y) = L(fx['x'], fx['y'])
            k = fx['type']
            if k in ('heart', 'star'):
                y += math.sin((fx['t'] + fx.get('seed', 0) * 10) * 0.35) * 3 * ss
                s = fx['size'] * ss
                alpha = 255 if fx['t'] < fx['max'] - 8 else max(0, int(255 * (fx['max'] - fx['t']) / 8))
                col = tuple(fx['color'][:3]) + (alpha,)
                if k == 'heart':
                    self._draw_heart(d, x, y, s, col)
                else:
                    self._draw_star(d, x, y, s, col)
                continue
            if k == 'bfx':
                r = fx.get('size', 5) * ss
                by = y - fx['t'] * 1 * ss
                alpha = 255 if fx['t'] < fx['max'] - 10 else max(0, int(255 * (fx['max'] - fx['t']) / 10))
                d.ellipse([x - r, by - r, x + r, by + r], outline=(150, 170, 190, alpha),
                          width=max(1, int(1.5 * ss)))
                d.ellipse([x - r * 0.55, by - r * 0.6, x - r * 0.05, by - r * 0.1],
                          fill=(255, 255, 255, min(255, alpha + 40)))
                continue
            if k == 'foam':
                s = fx.get('size', 4) * ss
                wob = math.sin((fx['t'] + fx.get('seed', 0) * 10) * 0.45) * 2.2 * ss
                fy = y - fx['t'] * 1.15 * ss
                alpha = 255 if fx['t'] < fx['max'] - 8 else max(0, int(255 * (fx['max'] - fx['t']) / 8))
                d.ellipse([x + wob - s, fy - s, x + wob + s, fy + s], outline=(150, 190, 210, alpha),
                          width=max(1, int(1.2 * ss)))
                d.ellipse([x + wob - s * 0.55, fy - s * 0.6, x + wob - s * 0.05, fy - s * 0.1],
                          fill=(255, 255, 255, min(255, alpha + 40)))
                continue
            if k == 'zzz':
                zs = (fx['t'] % 24) / 24
                fsz = max(8, int((6 + zs * 16) * ss))
                self._draw_text(d, 'z', x + zs * 8 * ss, y - zs * 26 * ss, fsz, (130, 120, 210, 200))
                continue
            if k == 'zdan':
                zsize = max(10, int(fx['size'] * ss))
                alpha = 255 if 8 <= fx['t'] < fx['max'] - 8 else max(0, int(255 * min(fx['t'], fx['max'] - fx['t']) / 8))
                self._draw_text_outline(d, 'Z', x, y, zsize, (140, 165, 235, alpha))
                continue
            if k == 'text':
                self._draw_bubble(d, fx, x, y, ss)
        if ss > 1:
            img = img.resize((w, h), Image.BILINEAR)  # v5.1.2:帧缩放用 BILINEAR(快 2~3 倍,超采样已保平滑)
        return (img, wx, wy)

    def _render(self):
        r = self._render_frame()
        if r is not None:
            self._push(r[0], r[1], r[2])

    # ---- 文字 ----
    def _draw_text(self, d, text, cx, cy, size, fill):
        font = self._get_font(size)
        bbox = d.textbbox((0, 0), text, font=font)
        th = bbox[3] - bbox[1]
        tw = bbox[2] - bbox[0]
        d.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), text, font=font, fill=fill)

    def _draw_text_outline(self, d, text, cx, cy, size, fill, outline=(255, 255, 255, 255)):
        '''带描边的大号文字(睡觉 Z 弹幕用, 明显醒目)'''
        font = self._get_font(size)
        bbox = d.textbbox((0, 0), text, font=font)
        th = bbox[3] - bbox[1]
        tw = bbox[2] - bbox[0]
        ox = cx - tw / 2 - bbox[0]
        oy = cy - th / 2 - bbox[1]
        o = max(1, int(size * 0.14))
        for dx, dy in ((-o, 0), (o, 0), (0, -o), (0, o), (-o, -o), (o, o), (-o, o), (o, -o)):
            d.text((ox + dx, oy + dy), text, font=font, fill=outline[:3] + (fill[3],))
        d.text((ox, oy), text, font=font, fill=fill)

    def _draw_bubble(self, d, fx, x, y, ss):
        '''对话气泡:圆角白底 + 描边 + 小尾巴 + 文字(带淡出)'''
        text = fx.get('text', '')
        size = max(12, int(17 * ss))
        font = self._get_font(size)
        bbox = d.textbbox((0, 0), text, font=font)
        th = bbox[3] - bbox[1]
        tw = bbox[2] - bbox[0]
        pad = 7 * ss
        by0 = y - th / 2 - pad
        bx0 = x - tw / 2 - pad
        by1 = y + th / 2 + pad
        bx1 = x + tw / 2 + pad
        alpha = 255 if fx['t'] < fx['max'] - 10 else max(0, int(255 * (fx['max'] - fx['t']) / 10))
        white = (255, 255, 255, alpha)
        d.rounded_rectangle([bx0, by0, bx1, by1], radius=10 * ss, fill=white)
        d.rounded_rectangle([bx0, by0, bx1, by1], radius=10 * ss, outline=C_MOUTH + (alpha,),
                            width=max(1, int(2 * ss)))
        d.polygon([(int(x - 6 * ss), int(by1)), (int(x + 6 * ss), int(by1)),
                   (int(x), int(by1 + 9 * ss))], fill=white)
        d.text((bx0 + pad - bbox[0], by0 + pad - bbox[1]), text, font=font, fill=(60, 70, 90, alpha))

    # ---- 蛇身 ----
    def _build_render_path(self, snake):
        '''把原始轨迹(世界坐标逐帧稳定)在折角处替换为圆弧, 返回 (x, y, dist) 列表。
        基于原始轨迹点计算 → 结果逐帧稳定, 转弯处像真实管子一样圆滑;
        跳过近 U 形折返(角平分线退化的噪声区), 杜绝幻影身体。'''
        raw = snake.path
        n = len(raw)
        if n < 6:
            return list(raw)
        R = BODY_R * 2.2
        out = []
        i = 0
        while i < n:
            (x, y, dist) = raw[i]
            if 0 < i < n - 1:
                (x0, y0, d0p) = raw[i - 1]
                (x1, y1, d1p) = raw[i + 1]
                v1x = x - x0
                v1y = y - y0
                v2x = x1 - x
                v2y = y1 - y
                L1 = math.hypot(v1x, v1y)
                L2 = math.hypot(v2x, v2y)
                if L1 > 1e-06 and L2 > 1e-06:
                    u1x = v1x / L1
                    u1y = v1y / L1
                    u2x = v2x / L2
                    u2y = v2y / L2
                    cos_a = max(-1, min(1, u1x * u2x + u1y * u2y))
                    if -0.9 <= cos_a <= 0.94:
                        sin_a = math.sqrt(max(0, 1 - cos_a * cos_a))
                        half = math.atan2(sin_a, 1 + cos_a)
                        bx = u1x + u2x
                        by = u1y + u2y
                        bl = math.hypot(bx, by)
                        if bl > 1e-06:
                            bx = bx / bl
                            by = by / bl
                            D = R / math.sin(half)
                            cross = u1x * u2y - u1y * u2x
                            if cross >= 0:
                                cx = x - bx * D
                                cy = y - by * D
                            else:
                                cx = x + bx * D
                                cy = y + by * D
                            t1 = (cx - x0) * u1x + (cy - y0) * u1y
                            ax = x0 + u1x * t1
                            ay = y0 + u1y * t1
                            t2 = (cx - x) * u2x + (cy - y) * u2y
                            bx2 = x + u2x * t2
                            by2 = y + u2y * t2
                            dA = d0p + t1
                            dB = dist + t2
                            if t1 >= 0 and t2 >= 0 and dB - dA > 1 and (out and dA > out[-1][2] + 0.5):
                                j = i
                                while j < n and raw[j][2] < dB - 0.5:
                                    j += 1
                                ang0 = math.atan2(ay - cy, ax - cx)
                                ang1 = math.atan2(by2 - cy, bx2 - cx)
                                da = ang1 - ang0
                                while da > math.pi:
                                    da -= 2 * math.pi
                                while da < -math.pi:
                                    da += 2 * math.pi
                                steps = max(2, int(abs(da) / 0.12) + 1)
                                for s in range(steps + 1):
                                    a = ang0 + da * s / steps
                                    dd = dA + (dB - dA) * s / steps
                                    out.append((cx + math.cos(a) * R, cy + math.sin(a) * R, dd))
                                i = j
                                continue
            out.append((x, y, dist))
            i += 1
        # v5.1.1:圆弧替换可能跳过路径末尾原始点,补上真实头端点保证衔接
        if out and (out[-1][0] != raw[-1][0] or out[-1][1] != raw[-1][1]):
            out.append((raw[-1][0], raw[-1][1], max(raw[-1][2], out[-1][2] + 2.0)))
        # v5.1.1:滑窗平滑,消除小转角折点的细小扭动(丝滑弯线)
        return self._smooth_path(out)

    def _sample_body(self, rp, d0, step, body_len):
        '''沿平滑轨迹按弧长采样身体点(世界坐标), 返回点列表。

        body_len 超过轨迹 XY 弧长时(补长被边界钳制/起步阶段),采样起点钳到路径起点,
        身体铺满全部轨迹,保证与头部衔接不脱节。

        [v5.2 修复 · 拖拽身体断层]
        原实现对「越界量」用**绝对容差**钳制: t>1 且 t<1.5 → 钳到段端点 q。
        这个容差是按安静档步距(QUIET_STEP=1.6px)标定的 —— 注释原文即
        「微小幅差(浮点/重算噪声)钳到段端」。但拎起时 _drag_head_to 每帧只落
        一个路径点, 段长 = DRAG_MAX_STEP = 30px; 于是 d 一进入某段, t 立刻>1,
        被钳到段端点 → 采样点实际被"吸附回原始折点", 相邻间距退化为段长本身。
        实测(78 节长蛇, 光标 400px/帧):
            正常游动  相邻绘制点距 max 11.53px  (无断裂)
            拖拽      相邻绘制点距 max 30.00~35.26px  (超过身直径 2*BODY_R=20px → 断层)
        修复: 改为「先走到真正包含 d 的那一段, 再插值」—— 与段长无关,
        任意段长下采样点都严格按弧长间隔 step 分布。
        '''
        L = rp[-1][2]
        lo = max(rp[0][2], L - body_len)
        hi = L - d0
        out = []
        m = len(rp)
        i = 0
        while i < m - 1 and rp[i + 1][2] < lo:
            i += 1
        d = lo
        guard = 0
        guard_max = m + int(max(0.0, hi - lo) / max(1e-6, step)) + 16
        while d <= hi and i < m - 1 and guard < guard_max:
            guard += 1
            p = rp[i]
            q = rp[i + 1]
            span = q[2] - p[2]
            if span <= 1e-09:
                i += 1
                continue
            if d < p[2]:
                d = p[2]          # 只可能由浮点噪声触发(前进方向单调)
            if d > q[2]:
                # d 已越过本段 → 前进到真正包含 d 的段,本段不落点
                i += 1
                continue
            t = (d - p[2]) / span
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
            d += step
        return out

    # ---- 主题 ----
    def _theme(self):
        tid = self.cfg.get('theme') or DEFAULT_THEME
        for t in SNAKE_THEMES:
            if t['id'] == tid:
                return t
        return SNAKE_THEMES[0]

    @staticmethod
    def _lerp_color(c1, c2, k):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))

    @staticmethod
    def _lighten(c, k):
        return tuple(int(c[i] + (255 - c[i]) * k) for i in range(3))

    @staticmethod
    def _rot_ellipse_pts(cx, cy, rx, ry, angle, n=14):
        '''旋转椭圆的多边形采样点(头部件用)'''
        ca, sa = math.cos(angle), math.sin(angle)
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            ex, ey = math.cos(a) * rx, math.sin(a) * ry
            pts.append((cx + ex * ca - ey * sa, cy + ex * sa + ey * ca))
        return pts

    # ---- 蛇身七层绘制(P3):shadow/outline/fill/pattern/belly/head/hat ----
    @staticmethod
    def _smooth_path(pts, half=26.0, end_keep=30.0):
        '''v5.1.1 路径平滑:按弧长 ±half 窗口对顶点做滑动平均,消除小转角折点
        造成的"不平整路面"式细小扭动;两端窗口渐缩(end_keep)保证头尾贴合;
        平滑后按新几何重算弧长(单调)。双指针实现, O(n)。'''
        n = len(pts)
        if n < 7:
            return pts
        dists = [p[2] for p in pts]
        # dist 单调化(弧线插入的 dd 可能轻微超过后续点,防止窗口计算出负 keep)
        for i in range(1, n):
            if dists[i] < dists[i - 1]:
                dists[i] = dists[i - 1]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        d_last = dists[-1]
        out = []
        j = 0
        k = 0
        for i in range(n):
            while j < i and dists[i] - dists[j] > half:
                j += 1
            while k + 1 < n and dists[k] - dists[i] < half:
                k += 1
            sx = sy = 0.0
            for t in range(j, k + 1):
                sx += xs[t]
                sy += ys[t]
            cnt = k - j + 1
            d_head = d_last - dists[i]
            d_tail = dists[i] - dists[0]
            # 端部(end_keep 内)保持原位(keep→1=不平滑),中段完全平滑(keep→0)
            smooth = min(1.0, min(d_head, d_tail) / end_keep) if end_keep > 0 else 1.0
            keep = 1.0 - smooth
            out.append((xs[i] * keep + sx / cnt * (1 - keep),
                        ys[i] * keep + sy / cnt * (1 - keep)))
        res = [(out[0][0], out[0][1], 0.0)]
        acc = 0.0
        for i in range(1, n):
            acc += math.hypot(out[i][0] - out[i - 1][0], out[i][1] - out[i - 1][1])
            res.append((out[i][0], out[i][1], acc))
        return res

    def _draw_snake(self, d, snake, ss, wx, wy):
        th = self._theme()
        d0 = HEAD_R * 1.1   # v5.1.1:身体更深地探入头下,保证衔接不脱节
        step = 5 if snake.body_len <= 1200 else 8
        rp = self._build_render_path(snake)
        pts = self._sample_body(rp, d0, step, snake.body_len)
        pts.reverse()
        if len(pts) < 3:
            return None
        loc = [((px - wx) * ss, (py - wy) * ss) for (px, py) in pts]
        n = len(loc)

        def taper(t):
            # P3:锥形身体 头 1.0 → 尾 0.55;body_scale 为 P6 胖瘦,P6 体型系数作用于身半径
            fat = getattr(self, 'body_scale', 1.0)
            stage = getattr(self, '_stage_render', 1.0)
            return max(4.0, BODY_R * (1.0 - (1.0 - TAPER_TAIL) * (t ** 0.9)) * fat * stage)

        rad = [taper(i / max(1, n - 1)) * ss for i in range(n)]
        if self.wag <= 0 and n >= 7:
            for off in range(1, 5):
                idx = n - off - 1
                if idx >= 2:
                    lift = math.sin((off / 4) * math.pi * 0.55) * 3.2 * ss
                    loc[idx] = (loc[idx][0], loc[idx][1] - lift)
        if getattr(self, '_last_active', True):
            self._draw_body_shadow(d, loc, rad, ss)
        self._draw_body_outline(d, loc, rad, ss, th['outline'])
        self._draw_body_fill(d, loc, rad, ss, th)
        self._draw_belly_stripe(d, loc, rad, ss, th)
        self._draw_body_pattern(d, loc, rad, ss, th)
        return None

    @staticmethod
    def _body_tangents(loc):
        tans = []
        for i in range(len(loc)):
            if i == 0:
                dx = loc[1][0] - loc[0][0]
                dy = loc[1][1] - loc[0][1]
            elif i == len(loc) - 1:
                dx = loc[-1][0] - loc[-2][0]
                dy = loc[-1][1] - loc[-2][1]
            else:
                dx = loc[i + 1][0] - loc[i - 1][0]
                dy = loc[i + 1][1] - loc[i - 1][1]
            L = math.hypot(dx, dy) or 1.0
            tans.append((dx / L, dy / L))
        return tans

    def _draw_body_shadow(self, d, loc, rad, ss):
        '''第 1 层:身体投影(半透明深色向下偏移 2px)'''
        sh = (20, 60, 40, 60)
        for (x, y), r in zip(loc, rad):
            d.ellipse([x - r, y - r + 2 * ss, x + r, y + r + 2 * ss], fill=sh)

    @staticmethod
    def _draw_body_outline(d, loc, rad, ss, outline):
        '''第 2 层:深色外轮廓(半径 +2.5px 圆串)'''
        for (x, y), r in zip(loc, rad):
            r2 = r + 2.5 * ss
            d.ellipse([x - r2, y - r2, x + r2, y + r2], fill=outline + (255,))

    def _draw_body_fill(self, d, loc, rad, ss, th):
        '''第 3 层:锥形主体,沿体长在主题 4 色间渐变(受光面亮→背光面深)'''
        body = th['body']
        flash = self.flash > 0
        for i, ((x, y), r) in enumerate(zip(loc, rad)):
            t = i / max(1, len(loc) - 1)
            k = t * 3.0
            j = min(2, int(k))
            col = self._lerp_color(body[j], body[j + 1], k - j)
            if flash:
                col = tuple(int(c * 0.5 + 127.5) for c in col)
            d.ellipse([x - r, y - r, x + r, y + r], fill=col + (255,))

    def _draw_belly_stripe(self, d, loc, rad, ss, th):
        '''第 4 层:腹部浅色带(沿身体屏幕下侧 40% 半径宽)。
        v5.1.1 改用带 joint 的曲线描线,消除圆点链的波浪边'''
        tans = self._body_tangents(loc)
        belly = th['belly'] + (255,)
        stripe_pts = []
        widths = []
        for (x, y), r, (tx, ty) in zip(loc, rad, tans):
            nx, ny = -ty, tx
            if ny < 0:              # 取指向屏幕下侧的法向
                nx, ny = -nx, -ny
            if abs(ny) < 0.3:       # 近垂直段取右侧,保持连贯
                nx, ny = ty, -tx
            stripe_pts.append((x + nx * r * 0.42, y + ny * r * 0.42))
            widths.append(max(2, int(2 * r * 0.40)))
        if len(stripe_pts) < 2:
            return
        # 分块单次描线(joint='curve' 需在单次调用内才平滑),块宽取块内平均,块间共享端点
        chunk = 8
        for start in range(0, len(stripe_pts) - 1, chunk):
            end = min(len(stripe_pts) - 1, start + chunk)
            seg = stripe_pts[start:end + 1]
            if len(seg) < 2:
                continue
            w = max(2, int((widths[start] + widths[end]) / 2))
            d.line(seg, fill=belly, width=w, joint='curve')
        # 端头圆帽,避免起止端平切
        for idx in (0, len(stripe_pts) - 1):
            (sx, sy) = stripe_pts[idx]
            r_end = widths[idx] / 2.0
            d.ellipse([sx - r_end, sy - r_end, sx + r_end, sy + r_end], fill=belly)

    def _draw_body_pattern(self, d, loc, rad, ss, th):
        '''第 5 层:背部菱形斑(每 PATTERN_EVERY 采样节一枚,随身体半径缩放)'''
        tans = self._body_tangents(loc)
        pat = th['pattern'] + (255,)
        alt = th['pattern_alt'] + (255,)
        for i in range(6, len(loc) - 3, PATTERN_EVERY):
            (x, y), r, (tx, ty) = loc[i], rad[i], tans[i]
            nx, ny = -ty, tx
            s = max(2.5 * ss, r * 0.58)
            a = s * 1.25
            b = s * 0.72
            d.polygon([(x + tx * a, y + ty * a), (x + nx * b, y + ny * b),
                       (x - tx * a, y - ty * a), (x - nx * b, y - ny * b)], fill=pat)
            d.ellipse([x - s * 0.22, y - s * 0.30, x + s * 0.22, y + s * 0.14], fill=alt)

    # ---- 蛇头(P3 部件化):描边/吻部/眼(固定高光)/吐信/表情/腮红/鼻孔 ----
    def _draw_head(self, img, d, hx, hy, ss, heading, blinking, mood='normal', tilt_deg=0):
        th = self._theme()
        (ux, uy) = heading
        if tilt_deg:
            a = math.radians(tilt_deg)
            (c, s) = (math.cos(a), math.sin(a))
            (ux, uy) = (ux * c - uy * s, ux * s + uy * c)
        ang = math.atan2(uy, ux)
        R = HEAD_R * ss * getattr(self, '_stage_render', 1.0)  # P6 体型系数作用于头
        outline = th['outline']
        head_main = th['head']
        if self.flash > 0:
            head_main = tuple(int(c * 0.5 + 127.5) for c in head_main)
        belly = th['belly']
        pupil_col = th['pupil']
        sleeping = mood == 'sleep'
        # 贴图覆盖通道:sprites/snake_head.png(朝右蛇头)存在时整头替换(BASELINE §11)
        if getattr(self, '_sprite_head', None) is not None:
            self._paste_head_sprite(img, hx, hy, ss, ang)
            self._draw_hat_layer(img, hx, hy, ss, ang)
            return
        # 吐信(画在头底下一层,从吻部前伸出)
        if self.tongue > 0 and not sleeping:
            self._draw_tongue(d, hx, hy, R, ang, ss, th['tongue'])
        # 轮廓:头圆 +2.5px 深色描边(比 v4 +2 更细更精致)
        d.ellipse([hx - R - 2.5 * ss, hy - R - 2.5 * ss, hx + R + 2.5 * ss, hy + R + 2.5 * ss],
                  fill=outline + (255,))
        # 头顶受光面(柔和高光)
        d.ellipse([hx - R, hy - R, hx + R, hy + R], fill=head_main + (255,))
        sheen = self._lighten(head_main, 0.22)
        d.polygon(self._rot_ellipse_pts(hx - ux * 0.18 * R - 0.12 * R,
                                        hy - uy * 0.18 * R - 0.16 * R,
                                        R * 0.62, R * 0.48, ang), fill=sheen + (255,))
        # 吻部:浅色椭圆沿 heading 前移 0.35R
        sx = hx + ux * R * 0.35
        sy = hy + uy * R * 0.35
        d.polygon(self._rot_ellipse_pts(sx, sy, R * 0.62, R * 0.5, ang), fill=belly + (255,))
        # 鼻孔:吻部两侧两粒
        for sgn in (-1.0, 1.0):
            nxp = hx + ux * R * 0.72 - uy * sgn * R * 0.16
            nyp = hy + uy * R * 0.72 + ux * sgn * R * 0.16
            nr = R * 0.05
            d.ellipse([nxp - nr, nyp - nr, nxp + nr, nyp + nr], fill=outline + (255,))
        # 腮红
        for sgn in (-1.0, 1.0):
            bx = hx - uy * sgn * R * 0.62 + ux * R * 0.12
            by = hy + ux * sgn * R * 0.62 + uy * R * 0.12
            d.polygon(self._rot_ellipse_pts(bx, by, R * 0.17, R * 0.11, ang),
                      fill=th['blush'] + (255,))
        # 眼:白底 + 瞳孔 + 固定高光(高光相对瞳孔取屏幕左上,不随朝向/眨眼)
        eye_col = C_EYE
        for sgn in (-1.0, 1.0):
            ex = hx - uy * sgn * R * 0.38 + ux * R * 0.30
            ey = hy + ux * sgn * R * 0.38 + uy * R * 0.30
            if sleeping:
                d.line([ex - 4.2 * ss, ey, ex + 4.2 * ss, ey], fill=pupil_col + (255,),
                       width=max(1, int(2 * ss)))
                continue
            rw = R * 0.34
            rh = 1.3 if blinking else R * 0.34
            d.polygon(self._rot_ellipse_pts(ex, ey, rw, rh, ang), fill=eye_col + (255,))
            if blinking:
                continue
            prx = ex + ux * R * 0.10
            pry = ey + uy * R * 0.10
            pr = R * 0.17 if mood != 'hungry' else R * 0.11
            if mood == 'hungry':
                pry += 1.6 * ss
            d.ellipse([prx - pr, pry - pr, prx + pr, pry + pr], fill=pupil_col + (255,))
            hlr = max(1.0, R * 0.065)
            d.ellipse([prx - 0.07 * R - hlr, pry - 0.08 * R - hlr,
                       prx - 0.07 * R + hlr, pry - 0.08 * R + hlr], fill=eye_col + (255,))
        # 嘴(睡/饿/开心/普通)
        if sleeping:
            d.ellipse([hx - 2.6 * ss, hy + 4.5 * ss, hx + 2.6 * ss, hy + 7.5 * ss],
                      outline=th['mouth'] + (255,), width=max(1, int(2 * ss)))
        elif mood == 'hungry':
            d.ellipse([hx - 2.6 * ss, hy + 5.0 * ss, hx + 2.6 * ss, hy + 8.2 * ss],
                      fill=th['mouth'] + (255,))
        elif mood == 'happy':
            d.arc([hx - 6.2 * ss, hy + 2.5 * ss, hx + 6.2 * ss, hy + 9.5 * ss],
                  180, 360, fill=th['mouth'] + (255,), width=max(1, int(2 * ss)))
        else:
            d.arc([hx - 4.6 * ss, hy + 2.0 * ss, hx + 4.6 * ss, hy + 10.0 * ss],
                  180, 360, fill=th['mouth'] + (255,), width=max(1, int(2 * ss)))
        self._draw_hat_layer(img, hx, hy, ss, ang)

    def _draw_hat_layer(self, img, hx, hy, ss, ang):
        '''第 7 层:帽子(P4)——随朝向旋转,贴图 + 内置兜底双通道;帽位随体型系数。
        P5.1:pivot 佩戴线对齐锚点(不再整体居中贴,避免帽子盖住脸)'''
        hat_id = self._current_hat_id
        if hat_id is None:
            return
        R = HEAD_R * ss * getattr(self, '_stage_render', 1.0)
        got = self._hat_renderer.get(hat_id, R, ang)
        if got is None:
            return
        (spr, px_off, py_off, ax_frac, ay_frac) = got
        (anchor_x, anchor_y) = hat_anchor_pos(hx, hy, ang, (ax_frac, ay_frac), R)
        img.paste(spr, (int(anchor_x - px_off), int(anchor_y - py_off)), spr)

    def _draw_tongue(self, d, hx, hy, R, ang, ss, color):
        '''吐信动画:红色细长两叉,沿 heading 前伸 0.8R'''
        k = 1.0 - abs(self.tongue - TONGUE_FRAMES / 2.0) / (TONGUE_FRAMES / 2.0)  # 弹出-收回
        L = R * 0.8 * (0.55 + 0.45 * k)
        bx = hx + math.cos(ang) * (R * 0.92)
        by = hy + math.sin(ang) * (R * 0.92)
        mx = bx + math.cos(ang) * L * 0.55
        my = by + math.sin(ang) * L * 0.55
        tipx = bx + math.cos(ang) * L
        tipy = by + math.sin(ang) * L
        fork = L * 0.42
        a1 = ang + 0.5
        a2 = ang - 0.5
        w = max(1, int(1.6 * ss))
        d.line([bx, by, mx, my], fill=color + (255,), width=w)
        d.line([mx, my, mx + math.cos(a1) * fork, my + math.sin(a1) * fork],
               fill=color + (255,), width=w)
        d.line([mx, my, tipx + math.cos(a2) * fork - (tipx - mx) * 0.0,
                my + math.sin(a2) * fork], fill=color + (255,), width=w)

    def _paste_head_sprite(self, img, hx, hy, ss, ang):
        '''snake_head.png 覆盖:按朝向旋转后贴到头锚点(缩放至 2×头径)'''
        spr = self._sprite_head
        target = int(HEAD_R * 2.6 * ss)
        if spr.width != target:
            ratio = spr.height / max(1, spr.width)
            spr = spr.resize((target, max(1, int(target * ratio))), Image.LANCZOS)
        deg = math.degrees(-ang)
        rot = spr.rotate(deg, expand=True, resample=Image.BICUBIC)
        img.paste(rot, (int(hx - rot.width / 2), int(hy - rot.height / 2)), rot)

    # ---- 食物 ----
    def _draw_apple(self, img, d, x, y, ss):
        '''食物苹果:优先使用贴图(apple.png),否则内置绘制'''
        if self._sprite_apple is not None:
            spr = self._sprite_apple
            target = int(22 * ss)
            if spr.width != target:
                spr = spr.resize((target, target), Image.LANCZOS)
            img.paste(spr, (int(x - target / 2), int(y - target / 2)), spr)
            return
        d.ellipse([x - 8 * ss, y - 4 * ss, x + 8 * ss, y + 8 * ss], fill=C_FOOD_SHADE + (255,))
        r = 9 * ss
        d.ellipse([x - r, y - r, x + r, y + r], fill=C_FOOD + (255,))
        d.ellipse([x - 5 * ss, y - 7 * ss, x - 1 * ss, y - 3 * ss], fill=C_FOOD_HI + (255,))
        d.line([x + 1 * ss, y - 10 * ss, x + 3 * ss, y - 15 * ss], fill=C_FOOD_STEM + (255,),
               width=max(1, int(2 * ss)))
        d.ellipse([x - 2 * ss, y - 17 * ss, x + 7 * ss, y - 10 * ss], fill=C_FOOD_LEAF + (255,))
        d.line([x + 2 * ss, y - 14 * ss, x + 4 * ss, y - 12 * ss], fill=C_FOOD_LEAF_VEIN + (255,),
               width=max(1, int(ss)))

    # ---- 粒子形状 ----
    @staticmethod
    def _draw_heart(d, x, y, s, col):
        r = s * 0.55
        d.ellipse([x - r, y - r * 0.8, x, y + r * 0.2], fill=col)
        d.ellipse([x, y - r * 0.8, x + r, y + r * 0.2], fill=col)
        d.polygon([(int(x - r), int(y + r * 0.05)), (int(x + r), int(y + r * 0.05)),
                   (int(x), int(y + r * 1.35))], fill=col)

    @staticmethod
    def _draw_star(d, x, y, s, col):
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            r = s if i % 2 == 0 else s * 0.45
            pts.append((int(x + math.cos(ang) * r), int(y + math.sin(ang) * r)))
        d.polygon(pts, fill=col)

    # ---- 字体 ----
    def _get_font(self, size):
        if self._font_cache is None:
            self._font_cache = {}
        if size in self._font_cache:
            return self._font_cache[size]
        fonts_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
        font = None
        for name in ('msyh.ttc', 'msyhbd.ttc', 'simhei.ttf', 'msyhl.ttc', 'segoeui.ttf'):
            try:
                font = ImageFont.truetype(os.path.join(fonts_dir, name), size)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        self._font_cache[size] = font
        return self._font_cache[size]
