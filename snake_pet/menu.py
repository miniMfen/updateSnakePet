'''右键菜单 —— 独立分层窗口,行布局 + 命中表驱动(v4 行为,P7 将扩容承载新功能)。'''
import logging
import math
import random
import time

from PIL import Image, ImageDraw

from .config import save_config
from .constants import BODY_MAX, BODY_MIN, SEG, SNAKE_THEMES
from .hats import DEFAULT_REGISTRY as HAT_REGISTRY, HAT_IDS
from .platform_win import blit_image_to_window, create_layered_window, show_window


class MenuMixin:
    (MENU_PW, MENU_PAD, MENU_HEAD, MENU_ROWH) = (254, 12, 46, 38)

    @property
    def MENU_PH(self):
        # 行数含:开关×3 + 状态 + 帽子(折两行) + 卖萌 + 皮肤 + 成就 + 投喂 + 盘旋 + 长度 + 动作×2
        nrows = 3 + 1 + 2 + 1 + 1 + 1 + 1 + 1 + 1 + 2
        return self.MENU_PAD + self.MENU_HEAD + nrows * self.MENU_ROWH + self.MENU_PAD

    def _skin_chip_box(self, i, y):
        '''皮肤行第 i 枚 chip 的命中矩形(5 枚紧凑排布)'''
        rowh = self.MENU_ROWH
        pad = self.MENU_PAD
        pitch = 46
        cx = pad + i * pitch
        return (cx, y + (rowh - 30) // 2, cx + 42, y + (rowh - 30) // 2 + 30)

    HAT_GRID_LINES = (('自动', '摘掉', '夜帽', '圣诞', '皇冠'),
                      ('学士', '礼帽', '棒球', '蝴蝶结'))

    def _hat_chip_box(self, col, line, y):
        '''帽子网格第 line 行第 col 列 chip 的命中矩形(每行最多 5 枚紧凑排布)'''
        rowh = self.MENU_ROWH
        pad = self.MENU_PAD
        pitch = 46
        cx = pad + col * pitch
        yy = y + line * rowh + (rowh - 30) // 2
        return (cx, yy, cx + 42, yy + 30)

    def _ensure_menu_window(self):
        if self._menu_hwnd:
            return
        if self.headless:
            return
        self._menu_hwnd = create_layered_window('SnakePetMenu', self.MENU_PW, self.MENU_PH,
                                                topmost=True)

    def _track_menu(self, sx, sy):
        '''在 (sx, sy) 处打开持久菜单;点选项保持打开,点 × / 菜单外关闭'''
        self._ensure_menu_window()
        self.menu_open = True
        self.menu_rect = None
        self._menu_rows = []
        self._menu_hits = []
        self._menu_layout()
        w = self.MENU_PW
        h = self.MENU_PH
        x = int(sx) + 6
        y = int(sy) + 6
        if x + w > self.vw:
            x = max(0, int(sx) - w - 6)
        if y + h > self.vh:
            y = max(0, int(sy) - h - 6)
        self.menu_rect = (x, y, x + w, y + h)
        self._menu_open_t = time.monotonic()
        if not self.headless:
            img = self._render_menu_image()
            if not blit_image_to_window(self._menu_hwnd, img, self.menu_rect[0], self.menu_rect[1]):
                logging.warning('菜单首帧推送失败,关闭菜单')
                self._close_menu()
                return
            show_window(self._menu_hwnd, 5)

    def _close_menu(self):
        if self._menu_hwnd:
            show_window(self._menu_hwnd, 0)
        self.menu_open = False
        self.menu_rect = None
        self._menu_hits = []
        self._menu_rows = []

    def _reopen_menu(self):
        '''选项变更后原地重绘(菜单保持打开)'''
        self._menu_rows = []
        self._menu_hits = []
        if not self.menu_open or not self.menu_rect:
            return
        self._menu_layout()
        if not self.headless:
            img = self._render_menu_image()
            blit_image_to_window(self._menu_hwnd, img, self.menu_rect[0], self.menu_rect[1])

    def _menu_layout(self):
        '''生成菜单行布局与命中区域(面板局部坐标),并挂载处理回调'''
        cfg = self.cfg
        pw = self.MENU_PW
        y = self.MENU_PAD + self.MENU_HEAD
        rowh = self.MENU_ROWH

        def flip(key):
            # [P0-确认] 依据字节码 `flip.<locals>.cb`:先取反;autostart 走注册表成功才落盘
            def cb():
                new = not cfg[key]
                if key == 'autostart':
                    from .platform_win import set_autostart
                    if set_autostart(new):
                        cfg[key] = new
                        save_config(cfg)
                else:
                    cfg[key] = not cfg[key]
                    save_config(cfg)
                self._reopen_menu()
            return cb

        for key, label in (('no_eat', '不再吃食物'), ('no_spawn', '左键点击不再生成食物'),
                           ('autostart', '开机自启动')):
            self._menu_rows.append({
                'kind': 'toggle',
                'label': label,
                'on': bool(cfg[key]),
                'y': y,
                'h': rowh,
            })
            self._menu_hits.append((0, y, pw, y + rowh, flip(key)))
            y += rowh
        cur = ('auto', 'quiet', 'active').index(cfg['state'])
        self._menu_rows.append({
            'kind': 'chips',
            'label': '状态',
            'chips': [('自动', 0), ('安静', 1), ('活跃', 2)],
            'active': cur,
            'y': y,
            'h': rowh,
        })
        for i, tag in enumerate(('auto', 'quiet', 'active')):
            self._menu_hits.append(self._chip_box(i, y) + ((lambda v=tag: self._set_state(v)),))
        y += rowh
        hat_ids = ('auto', 'none') + HAT_IDS
        hat_names = ('自动', '摘掉') + tuple(HAT_REGISTRY[h]['name'] for h in HAT_IDS)
        cur_hat = self.cfg.get('hat', 'auto')
        if cur_hat not in hat_ids:
            cur_hat = 'auto'
        # 帽子行:9 枚 chips 折两行(5+4,布局扩容能力预演,P6/P7 菜单复用)
        self._menu_rows.append({
            'kind': 'hatgrid',
            'label': '帽子',
            'chips': list(zip(hat_names, hat_ids)),
            'active': cur_hat,
            'y': y,
            'h': rowh * 2,
        })
        name_of = dict(zip(hat_names, hat_ids))
        for line, names in enumerate(self.HAT_GRID_LINES):
            for col, nm in enumerate(names):
                self._menu_hits.append(self._hat_chip_box(col, line, y)
                                       + ((lambda v=name_of[nm]: self._set_hat(v)),))
        y += rowh * 2
        self._menu_rows.append({'kind': 'button', 'label': '卖萌一次…', 'y': y, 'h': rowh})
        self._menu_hits.append((0, y, pw, y + rowh, (lambda: self._do_moe())))
        y += rowh
        # P6 皮肤行:5 套,未解锁灰显(点击提示解锁条件)
        from .growth import skin_lock_hint
        skin_ids = tuple(t['id'] for t in SNAKE_THEMES)
        cur_skin = self.cfg.get('theme', skin_ids[0])
        if cur_skin not in skin_ids:
            cur_skin = skin_ids[0]
        self._menu_rows.append({
            'kind': 'skingrid',
            'label': '皮肤',
            'chips': [(t['name'][:2], tid) for t, tid in zip(SNAKE_THEMES, skin_ids)],
            'active': cur_skin,
            'y': y,
            'h': rowh,
        })
        for i, t in enumerate(SNAKE_THEMES):
            self._menu_hits.append(self._skin_chip_box(i, y)
                                   + ((lambda idx=i: self._pick_skin(idx)),))
        y += rowh
        n_ach, tot_ach = self._ach.count()
        self._menu_rows.append({
            'kind': 'achievement',
            'label': '成就 %d/%d' % (n_ach, tot_ach),
            'y': y,
            'h': rowh,
        })
        self._menu_hits.append((0, y, pw, y + rowh, (lambda: self._show_achievements())))
        y += rowh
        self._menu_rows.append({'kind': 'button', 'label': '投喂一个苹果', 'y': y, 'h': rowh,
                                'style': 'teal'})
        self._menu_hits.append((0, y, pw, y + rowh, (lambda: self._feed_one())))
        y += rowh
        self._menu_rows.append({'kind': 'button', 'label': '盘旋一次', 'y': y, 'h': rowh,
                                'style': 'teal'})
        self._menu_hits.append((0, y, pw, y + rowh, (lambda: self._start_coil())))
        y += rowh
        nseg = max(1, int(self.snake.body_len // SEG))
        self._menu_rows.append({
            'kind': 'length',
            'label': '蛇身长度',
            'value': '%d 节' % nseg,
            'y': y,
            'h': rowh,
        })
        (mrect, prect) = self._length_buttons(y)
        self._menu_hits.append(mrect + (self._shrink_one,))
        self._menu_hits.append(prect + (self._grow_one,))
        y += rowh
        for label, cb in (('清空所有食物', (lambda: setattr(self, 'foods', []))),
                          ('退出', (lambda: self.quit()))):
            self._menu_rows.append({'kind': 'action', 'label': label, 'y': y, 'h': rowh})
            self._menu_hits.append((0, y, pw, y + rowh, cb))
            y += rowh
        self._menu_hits.append((pw - 46, 6, pw - 2, 42, self._close_menu))

    def _set_state(self, v):
        self.cfg['state'] = v
        save_config(self.cfg)
        self._reopen_menu()

    def _set_hat(self, val):
        '''帽子选择:'auto'/'none'/帽 id;持久化到配置(P4)'''
        self.cfg['hat'] = val
        save_config(self.cfg)
        self._reopen_menu()

    def _set_theme(self, tid):
        '''切换配色主题(P3;P6 起由皮肤行接管,保留兼容)'''
        self.cfg['theme'] = tid
        save_config(self.cfg)
        self._reopen_menu()

    def _pick_skin(self, idx):
        '''选择皮肤:未解锁则气泡提示门槛;已解锁则切换并持久化'''
        from .constants import SNAKE_THEMES
        from .growth import skin_lock_hint, skin_unlocked
        t = SNAKE_THEMES[idx]
        if not skin_unlocked(idx, self._ach.counters.get('total_eaten', 0)):
            self._spawn_bubble(skin_lock_hint(idx) or '尚未解锁')
            return
        self.cfg['theme'] = t['id']
        save_config(self.cfg)
        self._reopen_menu()

    def _show_achievements(self):
        '''成就行点击:气泡播报最近解锁的 3 个成就名'''
        names = self._ach.names()
        if not names:
            self._spawn_bubble('还没有成就,加油呀~')
        else:
            self._spawn_bubble('最近:' + '、'.join(names[-3:]))

    def _chip_box(self, i, y):
        '''第 i 个 chip 的命中矩形(与 _render_menu_image 的布局一致)'''
        rowh = self.MENU_ROWH
        pw = self.MENU_PW
        pad = self.MENU_PAD
        label_w = 48
        cx = pad + label_w + 8 + i * 58
        return (cx, y + (rowh - 30) // 2, cx + 52, y + (rowh - 30) // 2 + 30)

    def _length_buttons(self, y):
        '''蛇身长度行的 − / ＋ 按钮矩形(与 _render_menu_image 布局一致)'''
        rowh = self.MENU_ROWH
        pw = self.MENU_PW
        pad = self.MENU_PAD
        bsize = 30
        top = y + (rowh - bsize) // 2
        plus = (pw - pad - bsize, top, pw - pad, top + bsize)
        minus = (plus[0] - 8 - bsize, top, plus[0] - 8, top + bsize)
        return (minus, plus)

    def _grow_one(self):
        '''菜单 ＋ :身体加长 1 节(从尾部向后延伸,不弹菜单)'''
        s = self.snake
        if s.body_len >= BODY_MAX:
            return
        s.body_len += SEG
        s.ensure_path_len(s.body_len + 40)
        self._reopen_menu()

    def _shrink_one(self):
        '''菜单 − :身体缩短 1 节,减掉的部分从尾巴消失并变成泡沫飞走'''
        s = self.snake
        if s.body_len <= BODY_MIN:
            return
        (tx, ty) = s.pos(s.body_len)
        s.body_len -= SEG
        for _ in range(9):
            ang = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            sp = random.uniform(0.5, 1.9)
            self._spawn_fx('foam', tx + random.uniform(-9, 9), ty + random.uniform(-7, 7),
                           vx=math.cos(ang) * sp, vy=math.sin(ang) * sp - 0.35,
                           size=random.uniform(3, 6), max=random.randint(30, 46),
                           seed=random.random())
        self._reopen_menu()

    def _render_menu_image(self):
        '''用 PIL 绘制菜单面板(全透明通道,圆角面板),返回图像'''
        ph = self.MENU_PH
        pw = self.MENU_PW
        pad = self.MENU_PAD
        img = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([2, 2, pw - 2, ph - 2], radius=14, fill=(252, 252, 252, 248),
                            outline=(110, 120, 130, 255), width=2)
        fh = self._get_font(16)
        d.text((pad, 14), 'SnakePet 设置', font=fh, fill=(60, 70, 90, 255))
        cx = pw - 30
        d.ellipse([cx - 13, 12, cx + 13, 38], fill=(235, 90, 90, 255))
        d.line([cx - 6, 18, cx + 6, 32], fill=(255, 255, 255, 255), width=3)
        d.line([cx + 6, 18, cx - 6, 32], fill=(255, 255, 255, 255), width=3)
        f15 = self._get_font(15)
        f14 = self._get_font(14)
        for row in self._menu_rows:
            y0 = row['y']
            y1 = y0 + row['h']
            d.line([pad, y0, pw - pad, y0], fill=(225, 228, 232, 255), width=1)
            if row['kind'] == 'toggle':
                bx = pad + 6
                by = y0 + (row['h'] - 20) // 2
                on = row['on']
                d.rounded_rectangle([bx, by, bx + 36, by + 20], radius=10,
                                    fill=(110, 200, 120, 255) if on else (205, 210, 215, 255))
                kx = bx + 26 if on else bx + 4
                d.ellipse([kx, by + 2, kx + 16, by + 18], fill=(255, 255, 255, 255))
                bb = d.textbbox((0, 0), row['label'], font=f15)
                d.text((pad + 48, y0 + (row['h'] - bb[3] - bb[1]) // 2 - bb[1]), row['label'],
                       font=f15, fill=(60, 70, 90, 255))
                continue
            if row['kind'] == 'hatgrid':
                d.text((pad, y0 + 4), row['label'], font=f15, fill=(80, 90, 105, 255))
                f13 = self._get_font(13)
                for line, names in enumerate(self.HAT_GRID_LINES):
                    for col, nm in enumerate(names):
                        hid = dict((n, h) for n, h in row['chips'])[nm]
                        (x0, yy0, x1, yy1) = self._hat_chip_box(col, line, y0)
                        on = hid == row['active']
                        cb = d.textbbox((0, 0), nm, font=f13)
                        tw = cb[2] - cb[0]
                        tx = x0 + (x1 - x0 - tw) // 2 - cb[0]
                        ty = yy0 + (yy1 - yy0 - cb[3] - cb[1]) // 2 - cb[1]
                        if on:
                            d.rounded_rectangle([x0, yy0, x1, yy1], radius=9,
                                                fill=(110, 200, 120, 255))
                            d.text((tx, ty), nm, font=f13, fill=(255, 255, 255, 255))
                            continue
                        d.rounded_rectangle([x0, yy0, x1, yy1], radius=9,
                                            fill=(255, 255, 255, 255),
                                            outline=(160, 170, 180, 255), width=2)
                        d.text((tx, ty), nm, font=f13, fill=(90, 100, 110, 255))
                continue
            if row['kind'] == 'chips':
                lb = d.textbbox((0, 0), row['label'], font=f15)
                d.text((pad, y0 + (row['h'] - lb[3] - lb[1]) // 2 - lb[1]), row['label'],
                       font=f15, fill=(80, 90, 105, 255))
                for i, (txt, idx) in enumerate(row['chips']):
                    (x0, yy0, x1, yy1) = self._chip_box(i, y0)
                    on = idx == row['active']
                    cb = d.textbbox((0, 0), txt, font=f14)
                    tw = cb[2] - cb[0]
                    tx = x0 + (x1 - x0 - tw) // 2 - cb[0]
                    ty = yy0 + (yy1 - yy0 - cb[3] - cb[1]) // 2 - cb[1]
                    if on:
                        d.rounded_rectangle([x0, yy0, x1, yy1], radius=9, fill=(110, 200, 120, 255))
                        d.text((tx, ty), txt, font=f14, fill=(255, 255, 255, 255))
                        continue
                    d.rounded_rectangle([x0, yy0, x1, yy1], radius=9, fill=(255, 255, 255, 255),
                                        outline=(160, 170, 180, 255), width=2)
                    d.text((tx, ty), txt, font=f14, fill=(90, 100, 110, 255))
                continue
            if row['kind'] == 'skingrid':
                lb = d.textbbox((0, 0), row['label'], font=f15)
                d.text((pad, y0 + (row['h'] - lb[3] - lb[1]) // 2 - lb[1]), row['label'],
                       font=f15, fill=(80, 90, 105, 255))
                f13 = self._get_font(13)
                from .growth import skin_unlocked
                total_eaten = self._ach.counters.get('total_eaten', 0)
                for i, (txt, tid) in enumerate(row['chips']):
                    (x0, yy0, x1, yy1) = self._skin_chip_box(i, y0)
                    on = tid == row['active']
                    unlocked = skin_unlocked(i, total_eaten)
                    cb = d.textbbox((0, 0), txt, font=f13)
                    tw = cb[2] - cb[0]
                    tx = x0 + (x1 - x0 - tw) // 2 - cb[0]
                    ty = yy0 + (yy1 - yy0 - cb[3] - cb[1]) // 2 - cb[1]
                    if on:
                        d.rounded_rectangle([x0, yy0, x1, yy1], radius=9, fill=(110, 200, 120, 255))
                        d.text((tx, ty), txt, font=f13, fill=(255, 255, 255, 255))
                        continue
                    fill = (255, 255, 255, 255) if unlocked else (225, 228, 232, 255)
                    txt_col = (90, 100, 110, 255) if unlocked else (170, 176, 184, 255)
                    d.rounded_rectangle([x0, yy0, x1, yy1], radius=9, fill=fill,
                                        outline=(160, 170, 180, 255), width=2)
                    d.text((tx, ty), txt, font=f13, fill=txt_col)
                continue
            if row['kind'] == 'achievement':
                bb = d.textbbox((0, 0), row['label'], font=f15)
                d.text((pad + 26, y0 + (row['h'] - bb[3] - bb[1]) // 2 - bb[1]), row['label'],
                       font=f15, fill=(120, 100, 60, 255))
                continue
            if row['kind'] == 'button':
                x1 = pw - pad - 26
                x0 = pad + 26
                yy0 = y0 + 4
                yy1 = y1 - 4
                fill = (120, 205, 200, 255) if row.get('style') == 'teal' else (255, 170, 195, 255)
                d.rounded_rectangle([x0, yy0, x1, yy1], radius=11, fill=fill)
                bb = d.textbbox((0, 0), row['label'], font=f15)
                bw = bb[2] - bb[0]
                bh = bb[3] - bb[1]
                d.text((x0 + (x1 - x0 - bw) // 2 - bb[0], yy0 + (yy1 - yy0 - bh) // 2 - bb[1]),
                       row['label'], font=f15, fill=(255, 255, 255, 255))
                continue
            if row['kind'] == 'length':
                lb = d.textbbox((0, 0), row['label'], font=f15)
                d.text((pad, y0 + (row['h'] - lb[3] - lb[1]) // 2 - lb[1]), row['label'],
                       font=f15, fill=(70, 80, 100, 255))
                vb = d.textbbox((0, 0), row['value'], font=f15)
                d.text((pad + 96, y0 + (row['h'] - vb[3] - vb[1]) // 2 - vb[1]), row['value'],
                       font=f15, fill=(50, 60, 80, 255))
                (mrect, prect) = self._length_buttons(y0)
                fb = self._get_font(18)
                d.rounded_rectangle(mrect, radius=8, fill=(255, 255, 255, 255),
                                    outline=(200, 90, 90, 255), width=2)
                mb = d.textbbox((0, 0), '-', font=fb)
                d.text((mrect[0] + (mrect[2] - mrect[0] - mb[2] - mb[0]) // 2 - mb[0],
                        mrect[1] + (mrect[3] - mrect[1] - mb[3] - mb[1]) // 2 - mb[1]),
                       '-', font=fb, fill=(200, 90, 90, 255))
                d.rounded_rectangle(prect, radius=8, fill=(110, 200, 120, 255))
                pb = d.textbbox((0, 0), '+', font=fb)
                d.text((prect[0] + (prect[2] - prect[0] - pb[2] - pb[0]) // 2 - pb[0],
                        prect[1] + (prect[3] - prect[1] - pb[3] - pb[1]) // 2 - pb[1]),
                       '+', font=fb, fill=(255, 255, 255, 255))
                continue
            bb = d.textbbox((0, 0), row['label'], font=f15)
            bh = bb[3] - bb[1]
            d.text((pad + 26, y0 + (row['h'] - bh) // 2 - bb[1]), row['label'], font=f15,
                   fill=(70, 80, 100, 255))
        return img

    def _menu_hit(self, gx, gy):
        try:
            r = self.menu_rect
            if not r:
                return
            (x0, y0, x1, y1) = r
            if not (x0 <= gx <= x1 and y0 <= gy <= y1):
                if time.monotonic() - self._menu_open_t < 0.25:
                    return
                self._close_menu()
                return
            (lx, ly) = (gx - x0, gy - y0)
            for (rx0, ry0, rx1, ry1, cb) in self._menu_hits:
                if rx0 <= lx <= rx1 and ry0 <= ly <= ry1:
                    cb()
                    return
        except Exception as e:
            logging.warning('菜单项处理失败: %r', e)
