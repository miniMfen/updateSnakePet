'''整帧 PIL 绘制 —— 蛇头/身体/食物/夜帽/文字气泡/菜单面板(v4 画法)。
纯 PIL,不碰任何 Win32 句柄;推送由 app 层完成。
作为 mixin 挂到 SnakePet 上,保持 v4 方法名与调用链不变。'''
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

from .constants import (BODY_R, C_BLUSH, C_CAP, C_CAP_EDGE, C_EFFECT, C_EYE, C_FOOD,
                        C_FOOD_HI, C_FOOD_LEAF, C_FOOD_LEAF_VEIN, C_FOOD_SHADE,
                        C_FOOD_STEM, C_MOUTH, C_PUPIL, HEAD_R, PAD, SEG)


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
        if self._is_night() and self._sprite_cap is not None:
            (hx, hy) = (segs[0][0], segs[0][1])
            cw = HEAD_R * 2.6
            ch = cw * self._cap_ratio
            pts.append((hx - cw / 2, hy - HEAD_R * 0.5 - ch))
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
        ss = 2 if w * h <= 1200000 else 1
        img = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0))
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
            img = img.resize((w, h), Image.LANCZOS)
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
        return out

    def _sample_body(self, rp, d0, step, body_len):
        '''沿平滑轨迹按弧长采样身体点(世界坐标), 返回点列表'''
        L = rp[-1][2]
        lo = L - body_len
        hi = L - d0
        out = []
        m = len(rp)
        i = 0
        while i < m - 1 and rp[i + 1][2] < lo:
            i += 1
        d = lo
        guard = 0
        while d <= hi and i < m - 1 and guard < 5000:
            guard += 1
            p = rp[i]
            q = rp[i + 1]
            span = q[2] - p[2]
            if span <= 1e-09:
                i += 1
                continue
            t = (d - p[2]) / span
            if t < 0 or t > 1:
                i += 1
                continue
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
            d += step
        return out

    def _draw_snake(self, d, snake, ss, wx, wy):
        '''游戏风格可爱蛇:连续圆润等宽身体 + 尾段平滑收细微微上翘 + 卡通描边。
        用逐点圆链绘制:宽度逐点连续插值、转弯处绝对圆滑。'''
        body = self._body_col
        if self.flash > 0:
            body = tuple(int(c * 0.5 + 127.5) for c in body)
        head_main = tuple(int(c * 0.72 + 71.4) for c in body)
        belly = tuple(int(c * 0.4 + 153) for c in body)
        gloss = tuple(int(c * 0.55 + 114.75) for c in body)
        outline = tuple(int(c * 0.6) for c in body)
        d0 = HEAD_R * 1.35
        step = 5 if snake.body_len <= 1200 else 8
        rp = self._build_render_path(snake)
        pts = self._sample_body(rp, d0, step, snake.body_len)
        pts.reverse()
        if len(pts) < 3:
            return None
        loc = [((px - wx) * ss, (py - wy) * ss) for (px, py) in pts]
        n = len(loc)

        def wr(t):
            # [P0-确认] 依据修复报告:半径带 wr(i/(n-1)) 锥度权重(v4 原设计)
            if t < 0.65:
                return BODY_R
            u = (t - 0.65) / 0.35
            return max(4, BODY_R * (1 - u * u * 0.6))

        rad = [wr(i / max(1, n - 1)) * ss for i in range(n)]
        if self.wag <= 0 and n >= 7:
            for off in range(1, 5):
                idx = n - off - 1
                if idx >= 2:
                    lift = math.sin((off / 4) * math.pi * 0.55) * 3.2 * ss
                    loc[idx] = (loc[idx][0], loc[idx][1] - lift)
        for i in range(n):
            r = rad[i] + 3 * ss
            d.ellipse([loc[i][0] - r, loc[i][1] - r, loc[i][0] + r, loc[i][1] + r],
                      fill=outline + (255,))
        for i in range(n):
            r = rad[i]
            d.ellipse([loc[i][0] - r, loc[i][1] - r, loc[i][0] + r, loc[i][1] + r],
                      fill=body + (255,))
        for i in range(n):
            r = max(1.5 * ss, rad[i] * 0.42)
            d.ellipse([loc[i][0] - r, loc[i][1] - r, loc[i][0] + r, loc[i][1] + r],
                      fill=gloss + (255,))
        self._head_palette = (head_main, belly, outline)
        return None

    # ---- 蛇头 ----
    def _draw_head(self, img, d, hx, hy, ss, heading, blinking, mood='normal', tilt_deg=0):
        '''内置绘制的可爱大头(游戏风格;支持心情表情/歪头/夜间睡帽)'''
        if hasattr(self, '_head_palette'):
            (head_main, belly, outline) = self._head_palette
        else:
            body = self._body_col
            head_main = tuple(int(c * 0.72 + 71.4) for c in body)
            belly = tuple(int(c * 0.4 + 153.0) for c in body)
            outline = tuple(int(c * 0.6) for c in body)
        R = HEAD_R * ss
        d.ellipse([hx - R - 2 * ss, hy - R - 2 * ss, hx + R + 2 * ss, hy + R + 2 * ss],
                  fill=outline + (255,))
        d.ellipse([hx - R, hy - R, hx + R, hy + R], fill=head_main + (255,))
        hr = R * 0.45
        d.ellipse([hx - hr - R * 0.3, hy - hr - R * 0.34,
                   hx + hr - R * 0.3, hy + hr - R * 0.34], fill=belly + (255,))
        (ux, uy) = heading
        if tilt_deg:
            a = math.radians(tilt_deg)
            (c, s) = (math.cos(a), math.sin(a))
            (ux, uy) = (ux * c - uy * s, ux * s + uy * c)
        (px2, py2) = (-uy, ux)
        sleeping = mood == 'sleep'
        # 眼白
        for i in range(2):
            s = 1.0 if i == 0 else -1.0
            ex = hx + px2 * s * 6.5 * ss + ux * 6.0 * ss
            ey = hy + py2 * s * 6.5 * ss + uy * 6.0 * ss
            if sleeping:
                d.line([ex - 4.2 * ss, ey, ex + 4.2 * ss, ey], fill=C_PUPIL + (255,),
                       width=max(1, int(2 * ss)))
                continue
            rw = 4.8 * ss
            rh = 1.3 if blinking else 4.8 * ss
            d.ellipse([ex - rw, ey - rh, ex + rw, ey + rh], fill=C_EYE + (255,))
        if not sleeping:
            # 瞳孔 + 高光
            for i in range(2):
                s = 1.0 if i == 0 else -1.0
                ex = hx + px2 * s * 6.5 * ss + ux * 9.2 * ss
                ey = hy + py2 * s * 6.5 * ss + uy * 9.2 * ss
                if mood == 'hungry':
                    (rw, rh) = (2.2 * ss, 2.2 * ss)
                    d.ellipse([ex - rw, ey - rh + 1.6 * ss, ex + rw, ey + rh + 1.6 * ss],
                              fill=C_PUPIL + (255,))
                    d.arc([ex - 5.2 * ss, ey - 4.8 * ss, ex + 5.2 * ss, ey + 3.0 * ss],
                          180, 360, fill=head_main + (255,), width=max(2, int(3 * ss)))
                    continue
                rw = 2.2 * ss
                rh = 0.9 if blinking else 2.2 * ss
                d.ellipse([ex - rw, ey - rh, ex + rw, ey + rh], fill=C_PUPIL + (255,))
                if blinking:
                    continue
                d.ellipse([ex - 1.3 * ss, ey - 1.5 * ss, ex + 0.7 * ss, ey + 0.5 * ss],
                          fill=C_EYE + (255,))
        # 腮红
        for i in range(2):
            s = 1.0 if i == 0 else -1.0
            bx = hx + px2 * s * 9.5 * ss + ux * 3.0 * ss
            by = hy + py2 * s * 9.5 * ss + ux * 3.0 * ss
            d.ellipse([bx - 3.0 * ss, by - 1.9 * ss, bx + 3.0 * ss, by + 1.9 * ss],
                      fill=C_BLUSH + (255,))
        # 嘴(睡/饿/开心/普通)
        if sleeping:
            d.ellipse([hx - 2.6 * ss, hy + 4.5 * ss, hx + 2.6 * ss, hy + 7.5 * ss],
                      outline=C_MOUTH + (255,), width=max(1, int(2 * ss)))
        elif mood == 'hungry':
            d.ellipse([hx - 2.6 * ss, hy + 5.0 * ss, hx + 2.6 * ss, hy + 8.2 * ss],
                      fill=C_MOUTH + (255,))
        elif mood == 'happy':
            d.arc([hx - 6.2 * ss, hy + 2.5 * ss, hx + 6.2 * ss, hy + 9.5 * ss],
                  180, 360, fill=C_MOUTH + (255,), width=max(1, int(2 * ss)))
        else:
            d.arc([hx - 4.6 * ss, hy + 2.0 * ss, hx + 4.6 * ss, hy + 10.0 * ss],
                  180, 360, fill=C_MOUTH + (255,), width=max(1, int(2 * ss)))
        if mood in ('normal', 'happy'):
            tx0 = hx - 2.2 * ss
            ty0 = hy + 9.8 * ss
            d.rounded_rectangle([tx0, ty0, tx0 + 4.4 * ss, ty0 + 5.4 * ss], radius=2.0 * ss,
                                fill=(255, 140, 160, 255), outline=outline + (255,),
                                width=max(1, int(1.2 * ss)))
        if self._is_night():
            self._draw_night_cap(img, d, hx, hy, ss, heading=heading)

    def _draw_night_cap(self, img, d, hx, hy, ss, r=None, heading=(0, -1)):
        '''夜间睡帽:优先使用 sprites/cap.png 贴图(戴端正不旋转);无贴图手绘锥形帽兜底'''
        if self._sprite_cap is not None:
            spr = self._sprite_cap
            R = (r or HEAD_R) * ss
            target_w = max(12, int(R * 2.6))
            target_h = max(12, int(target_w * self._cap_ratio))
            if spr.width != target_w or spr.height != target_h:
                spr = spr.resize((target_w, target_h), Image.LANCZOS)
            img.paste(spr, (int(hx - spr.width / 2), int(hy - R * 0.5 - spr.height)), spr)
            return
        R = (r or HEAD_R) * ss
        left = hx - R * 1.0
        right = hx + R * 1.0
        d.polygon([(int(left), int(hy - R * 0.15)), (int(right), int(hy - R * 0.15)),
                   (int(hx), int(hy - R * 1.55))], fill=C_CAP)
        d.arc([left, hy - R * 0.9, right, hy + R * 0.3], 180, 360, fill=C_CAP_EDGE,
              width=max(2, int(3 * ss)))
        (bx, by) = (hx, hy - R * 1.55)
        d.ellipse([bx - 4.5 * ss, by - 4.5 * ss, bx + 4.5 * ss, by + 4.5 * ss],
                  fill=(255, 255, 255, 255))

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
