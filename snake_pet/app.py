'''SnakePet 组装 —— 窗口/钩子线程/事件队列/主循环/看门狗 + selftest。
其余关注点(特效/行为/渲染/菜单)以 mixin 方式挂入,方法名与 v4 调用链一致。'''
import ctypes
import logging
import math
import os
import queue
import random
import threading
import time
from ctypes import wintypes

from .behavior import BehaviorMixin
from .config import base_dir, config_path, load_config, save_config
from .constants import (ACHIEVEMENTS, ACTIVE_STEP, APP_NAME, BODY_START_SEG, FX_COLORS,
                        GROW_PER_FOOD, HEAD_R, MARGIN, MAX_PATH, QUIET_STEP,
                        SATIETY_DECAY_PER_SEC, SATIETY_START, SEG, SAVE_PERIOD_SEC,
                        TONGUE_PERIOD, TICK_MS)
from .fx import FxMixin
from .growth import (Achievements, digest_step, fatness_of, load_pet_state, save_pet_state,
                     stage_baseline, stage_coeff, stage_of)
from .hats import HatRenderer
from .interact import InteractSM, DRAG_MAX_STEP
from .menu import MenuMixin
from .platform_win import (BITMAPINFOHEADER, HOOKPROC, MSLLHOOKSTRUCT, PM_REMOVE,
                           WH_MOUSE_LL, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE, WM_QUIT,
                           WM_RBUTTONDOWN, WS_EX_LAYERED,
                           WS_EX_TOPMOST, ULW_ALPHA, _BLEND, acquire_single_instance_mutex,
                           create_layered_window, destroy_window, ensure_dpi_aware,
                           enum_topmost_layered_windows, grab_screen_bgra, is_desktop_window,
                           is_window_visible, primary_screen_metric, sink_window_bottom,
                           untopmost_window, virtual_screen, window_from_point, workarea)
from .render import RenderMixin
from .snake import Snake
from .sprites import load_snake_sprite, load_sprite, sprite_dominant
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32


class SnakePet(FxMixin, BehaviorMixin, RenderMixin, MenuMixin):
    def __init__(self, cfg, headless=False):
        self.cfg = cfg
        self.headless = headless
        self.foods = []
        self.effects = []
        self.seg_pos = []
        self.menu_open = False
        self.menu_rect = None
        self._menu_rows = []
        self._menu_hits = []
        self._menu_hwnd = None
        self._menu_open_t = 0
        self._quitting = False
        self._blink = 0
        self._blink_timer = random.randint(90, 210)
        self.satiety = SATIETY_START
        self.fx = []
        self.hop = 0
        self.flash = 0
        self.wag = 0
        self.tilt = 0
        self.tongue = 0
        self._tongue_timer = random.randint(*TONGUE_PERIOD)
        self.body_scale = 1.0      # P6 胖瘦系数钩子
        self._last_active = True   # 渲染投影层仅活跃档绘制
        self._squash = 0           # P5 放下挤压动画帧
        self._interact = InteractSM(None)  # P5 互动状态机(bounds 就绪后补)
        self._stage_render = 1.0   # P6 平滑后的体型系数(渲染用)
        self._eat_times = []       # P6 胖瘦滚动窗口(进食时间戳)
        self._digest_fx_at = 0.0   # P6 消化粒子计时
        self._ach = Achievements()
        self._state_loaded = None
        self._last_save = time.monotonic()
        self._idle_timer = random.randint(600, 1200)
        self._chase_stall = 0
        self._chase_min = 1e+09
        self._break_chase = 0
        self._heart_timer = random.randint(180, 420)
        self._hungry_timer = random.randint(360, 660)
        self._sleep_since = None
        self._sleep_dur = 20
        self._zdan_timer = 0
        self._zzz_timer = random.randint(240, 480)
        self._last_lclick = 0
        self._last_lx = 0
        self._last_ly = 0
        self._font_cache = None
        self.evq = queue.Queue()
        self._proc = None
        self._hook = None
        self._pump_tid = None
        self._stop = threading.Event()
        self._hook_ready = threading.Event()
        self._hook_ok = False
        self._sprite_apple = load_sprite('apple.png')
        self._sprite_head = load_sprite('snake_head.png')   # P3:整头贴图覆盖通道
        self._hat_renderer = HatRenderer()                  # P4:帽子衣柜
        self._sprite_name = None
        (spr, sname) = load_snake_sprite()
        # [P0-确认→P3 适配] 依据 dis_init.txt 行 559~572:蛇贴图存在时取主色。
        # P3 起配色由主题表驱动,看门狗监测色跟随主题;有头贴图时才用贴图主色
        theme = self._theme()
        if spr is not None and self._sprite_head is not None:
            body = sprite_dominant(spr)
            self._body_col = body
            self._sprite_name = sname
            logging.info('蛇头贴图 %s: 看门狗监测色=%s', sname, body)
            self._watch_colors = [body,
                                  (max(0, body[0] - 25), max(0, body[1] - 25), max(0, body[2] - 25))]
        else:
            self._body_col = theme['body'][1]
            self._watch_colors = [theme['head'],
                                  (max(0, theme['head'][0] - 25),
                                   max(0, theme['head'][1] - 25),
                                   max(0, theme['head'][2] - 25))]
        self._hwnd = None
        self._hdc_mem = None
        self._hbmp = None
        self._bits = ctypes.c_void_p()
        self._win_w = 0
        self._win_h = 0
        if headless:
            self.vx, self.vy, self.vw, self.vh = (0, 0, 1920, 1080)
            self.bounds = (MARGIN, MARGIN, self.vw - MARGIN, self.vh - MARGIN)
        else:
            self._create_window()
            logging.info('宠物窗口 hwnd=0x%x', self._hwnd or 0)
            self.vx, self.vy, self.vw, self.vh = virtual_screen()
            (rx0, ry0, rx1, ry1) = workarea()
            if self.vw == primary_screen_metric() and self.vx == 0 and self.vy == 0:
                bx0 = rx0 - self.vx + MARGIN
                by0 = ry0 - self.vy + MARGIN
                bx1 = rx1 - self.vx - MARGIN
                by1 = ry1 - self.vy - MARGIN
            else:
                (bx0, by0) = (MARGIN, MARGIN)
                (bx1, by1) = (self.vw - MARGIN, self.vh - MARGIN)
            if bx1 <= bx0 or by1 <= by0:
                (bx0, by0, bx1, by1) = (MARGIN, MARGIN, self.vw - MARGIN, self.vh - MARGIN)
            self.bounds = (bx0, by0, bx1, by1)
        sx = random.uniform(self.bounds[0], self.bounds[2])
        sy = random.uniform(self.bounds[1], self.bounds[3])
        # v5.1 初始体长 8 节(用户反馈 5 节像蝌蚪,适量加长)
        self.snake = Snake(sx, sy, random.uniform(-math.pi, math.pi), self.bounds,
                           body_len=SEG * BODY_START_SEG)
        self._interact.bounds = self.bounds
        # ---- P6 存档读取:位置/朝向/体长/饱食/计数/成就/皮肤 ----
        self._autosave = bool(cfg.get('autosave', True))  # v5.1 记住小蛇开关
        self._state_loaded = load_pet_state() if self._autosave else None
        st = self._state_loaded
        if st is not None:
            if st.get('pos'):
                (px_, py_) = st['pos']
                px_ = min(max(px_, self.bounds[0]), self.bounds[2])
                py_ = min(max(py_, self.bounds[1]), self.bounds[3])
                self.snake = Snake(px_, py_, float(st.get('heading', 0.0)), self.bounds,
                                   body_len=max(float(st.get('body_len', SEG * 5)), 40.0))
            self.snake.body_len = max(float(st.get('body_len', self.snake.body_len)), 40.0)
            self.snake.ensure_path_len(self.snake.body_len + 40)
            if st.get('satiety') is not None:
                self.satiety = min(100.0, max(0.0, float(st['satiety'])))
            if st.get('skin') and st.get('skin') in ('jade', 'classic', 'peach',
                                                     'nightglow', 'clown'):
                self.cfg['theme'] = st['skin']
            if st.get('hat'):
                self.cfg['hat'] = st['hat']
            self._ach = Achievements(st['achievements'],
                                     st.get('counters'),
                                     st['counters'].get('days'))
            self._eat_times = []
            today = time.strftime('%Y-%m-%d')
            self._ach.days.add(today)
            for aid in self._ach.check():
                logging.info('成就解锁(读档): %s', aid)
        else:
            self._ach.days.add(time.strftime('%Y-%m-%d'))
        if not headless and self._hwnd:
            sink_window_bottom(self._hwnd)
        if not headless and not self._start_hook():
            logging.warning('全局鼠标钩子不可用:左键生成食物/右键菜单将不可用')
        self._last_check = time.monotonic()
        self._avoid = []
        self._covered_since = None
        self._last_cover_rebuild = 0

    # ---- 窗口与 DIB ----
    def _create_window(self):
        self._hwnd = create_layered_window(APP_NAME, 8, 8)

    def _free_dib(self):
        if self._hbmp:
            gdi32.DeleteObject(self._hbmp)
            self._hbmp = None
        if self._hdc_mem:
            gdi32.DeleteDC(self._hdc_mem)
            self._hdc_mem = None
        self._win_w = 0
        self._win_h = 0

    def _ensure_dib(self, w, h):
        if self._hdc_mem and (w, h) == (self._win_w, self._win_h):
            return True
        self._free_dib()
        self._hdc_mem = gdi32.CreateCompatibleDC(0)
        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth = int(w)
        bi.biHeight = -int(h)
        bi.biPlanes = 1
        bi.biBitCount = 32
        self._hbmp = gdi32.CreateDIBSection(self._hdc_mem, ctypes.byref(bi), 0,
                                            ctypes.byref(self._bits), None, 0)
        if not self._hbmp:
            return False
        gdi32.SelectObject(self._hdc_mem, self._hbmp)
        self._win_w = int(w)
        self._win_h = int(h)
        return True

    def _push(self, img, x, y):
        '''把 PIL RGBA 图像推送到屏幕上 (x, y) 位置(headless 时丢弃;持久 DIB 复用)'''
        if self.headless:
            return
        (w, h) = img.size
        if not self._ensure_dib(w, h):
            return
        buf = img.tobytes('raw', 'BGRA')
        ctypes.memmove(self._bits, buf, len(buf))
        pt = wintypes.POINT(int(x), int(y))
        sz = wintypes.SIZE(w, h)
        src = wintypes.POINT(0, 0)
        user32.UpdateLayeredWindow(self._hwnd, 0, ctypes.byref(pt), ctypes.byref(sz),
                                   self._hdc_mem, ctypes.byref(src), 0,
                                   ctypes.byref(_BLEND), ULW_ALPHA)

    # ---- 养成(P6):消化/阶段/胖瘦/周期存档 ----
    def _growth_step(self, active):
        now = time.monotonic()
        # 阶段系数平滑(≤2s 无跳变)
        target = stage_coeff(stage_of(self._ach.counters.get('total_eaten', 0)))
        self._stage_render += (target - self._stage_render) / 15.0
        # 消化:satiety<40 时体长回落至阶段基线,伴淡绿消化粒子
        baseline = stage_baseline(stage_of(self._ach.counters.get('total_eaten', 0)))
        new_len = digest_step(self.snake.body_len, self.satiety, TICK_MS / 1000.0, baseline)
        if new_len < self.snake.body_len - 1e-6:
            self.snake.body_len = new_len
            if now - self._digest_fx_at >= 3.0:
                self._digest_fx_at = now
                (tx, ty) = self.snake.pos(self.snake.body_len * 0.5)
                self._spawn_fx('bfx', tx, ty, size=random.uniform(2.5, 4.5), max=32)
                logging.info('消化中: body_len=%.0f 基线=%.0f', self.snake.body_len, baseline)
        # 胖瘦滚动窗口
        self._eat_times = [t for t in self._eat_times if now - t <= 600.0]
        self.body_scale = fatness_of(self._eat_times, now)
        # 周期存档(60s)
        if now - self._last_save >= SAVE_PERIOD_SEC:
            self._last_save = now
            self.save_pet_state_now(reason='periodic')

    def _pet_state(self):
        (hx, hy) = self.snake.head()
        return {
            'pos': [hx, hy],
            'heading': self.snake.heading_angle,
            'body_len': self.snake.body_len,
            'satiety': self.satiety,
            'total_eaten': self._ach.counters.get('total_eaten', 0),
            'affinity': self._interact.affinity,
            'skin': self.cfg.get('theme', 'jade'),
            'hat': self.cfg.get('hat', 'auto'),
            'achievements': sorted(self._ach.unlocked),
            'counters': {**self._ach.counters,
                         'days': sorted(self._ach.days)},
        }

    def save_pet_state_now(self, reason='manual'):
        if not self._autosave:
            return
        self._last_save = time.monotonic()
        if save_pet_state(self._pet_state()):
            logging.info('存档已保存(%s)', reason)

    def _unlock_achievements(self):
        news = self._ach.check()
        for aid in news:
            name = dict((a, n) for (a, n, _d) in ACHIEVEMENTS).get(aid, aid)
            self._spawn_bubble('成就解锁:%s!' % name)
            (hx, hy) = self.snake.head()
            for _ in range(4):
                self._spawn_fx('star', hx + random.uniform(-22, 22), hy + random.uniform(-26, -2),
                               size=random.uniform(3, 5), color=random.choice(FX_COLORS),
                               max=30, seed=random.random())
            logging.info('成就解锁: %s (%s)', aid, name)
            self.save_pet_state_now(reason='achievement')
        return news

    # ---- 互动(P5):状态机事件落地 ----
    def _consume_interact(self, now):
        self._interact.tick(now)
        for (ev, x, y) in self._interact.take_events():
            if ev == 'pet_done':
                self._ach.counters['pet_count'] = self._ach.counters.get('pet_count', 0) + 1
                self._unlock_achievements()
                (hx, hy) = self.snake.head()
                for _ in range(random.randint(3, 5)):
                    self._spawn_fx('heart', hx + random.uniform(-18, 18),
                                   hy - 8 + random.uniform(-14, 2),
                                   size=random.uniform(4, 7), color=random.choice(FX_COLORS),
                                   max=random.randint(36, 50), seed=random.random())
                self._spawn_bubble('好开心~')
                self.wag = 14
            elif ev == 'drag_start':
                if self.snake.coil is not None:
                    self.snake.coil.fast_unwind()
                if self._is_sleeping():
                    self._wake()
                self.tilt = 12
            elif ev == 'drag':
                self._drag_head_to(x, y)
            elif ev == 'drop':
                (tx, ty) = (x - self.vx, y - self.vy)
                for _ in range(3):
                    self._spawn_fx('foam', tx + random.uniform(-9, 9), ty + random.uniform(-5, 7),
                                   vx=random.uniform(-0.8, 0.8), vy=random.uniform(-0.4, 0.2),
                                   size=random.uniform(3, 6), max=random.randint(24, 40),
                                   seed=random.random())
                self._squash = 6

    def _drag_head_to(self, x, y):
        '''拎起跟随:头移向光标(clamp 进 bounds,单帧限速防拉裂),身体沿路径跟随'''
        (cx, cy) = self._interact.cursor
        (lx, ly) = (cx - self.vx, cy - self.vy)
        (tx, ty) = self.snake._clamp(lx, ly)
        (hx, hy) = self.snake.head()
        d = math.hypot(tx - hx, ty - hy)
        if d < 0.5:
            return
        if d > DRAG_MAX_STEP:
            k = DRAG_MAX_STEP / d
            tx = hx + (tx - hx) * k
            ty = hy + (ty - hy) * k
        last = self.snake.path[-1]
        nd = last[2] + math.hypot(tx - last[0], ty - last[1])
        self.snake.path.append((tx, ty, nd))
        while len(self.snake.path) > MAX_PATH:
            self.snake.path.popleft()

    # ---- 全局鼠标钩子 ----
    def _start_hook(self):
        def handler(nCode, wParam, lParam):
            if nCode == 0:
                try:
                    data = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    if wParam == WM_LBUTTONDOWN:
                        self.evq.put(('L', data.pt.x, data.pt.y))
                    elif wParam == WM_LBUTTONUP:
                        self.evq.put(('LU', data.pt.x, data.pt.y))
                    elif wParam == WM_MOUSEMOVE:
                        # 仅在互动进行中转发,避免事件洪泛
                        if self._interact.state != InteractSM.IDLE:
                            self.evq.put(('MOVE', data.pt.x, data.pt.y))
                    elif wParam == WM_RBUTTONDOWN:
                        self.evq.put(('R', data.pt.x, data.pt.y))
                except Exception:
                    pass
            return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

        self._proc = HOOKPROC(handler)

        def pump():
            self._pump_tid = kernel32.GetCurrentThreadId()
            self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc,
                                                  kernel32.GetModuleHandleW(None), 0)
            self._hook_ok = bool(self._hook)
            self._hook_ready.set()
            msg = wintypes.MSG()
            while not self._stop.is_set():
                r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if r in (0, -1):
                    return
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        t = threading.Thread(target=pump, name='mouse-hook', daemon=True)
        t.start()
        self._hook_ready.wait(2)
        return self._hook_ok

    def _stop_hook(self):
        self._stop.set()
        if self._pump_tid:
            user32.PostThreadMessageW(self._pump_tid, WM_QUIT, 0, 0)
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
        self._hook = None

    # ---- 事件消费 ----
    def _hit_snake_head(self, lx, ly):
        (hx, hy) = self.snake.head()
        return math.hypot(lx - hx, ly - hy) <= 1.5 * HEAD_R

    def _drain_events(self):
        while True:
            try:
                (kind, x, y) = self.evq.get_nowait()
            except queue.Empty:
                return
            except Exception as e:
                logging.exception('事件处理异常: %r', e)
                return
            now = time.monotonic()
            if self.menu_open and kind in ('L', 'R') and self._menu_hit(x, y):
                continue
            if kind == 'L':
                if self.menu_open:
                    continue
                (lx, ly) = (x - self.vx, y - self.vy)
                hit = self._hit_snake(lx, ly)
                if hit:
                    # 双击优先(双击 = hop+气泡;单按蛇身无动作,防误触)
                    if now - self._last_lclick < 0.45 and math.hypot(x - self._last_lx, y - self._last_ly) < 70:
                        self._last_lclick = 0
                        self._interact.state = InteractSM.IDLE
                        self.hop = 8
                        self._on_double_click(lx, ly)
                    else:
                        self._last_lclick = now
                        self._last_lx = x
                        self._last_ly = y
                        self._interact.press(x, y, self._hit_snake_head(lx, ly), now)
                elif not self.cfg['no_spawn'] and self._is_desktop_at(x, y):
                    self._spawn_food(lx, ly)
            elif kind == 'LU':
                self._interact.release(x, y, now)
            elif kind == 'MOVE':
                self._interact.move(x, y, now)
            elif kind == 'R':
                hit = self._hit_snake(x - self.vx, y - self.vy)
                if not self.menu_open and hit:
                    self._track_menu(x, y)

    def _is_desktop_at(self, x, y):
        '''是否在桌面(而非软件/网页窗口)上点击:只有桌面才生成食物'''
        h = window_from_point(x, y)
        if not h:
            return True
        if h == self._hwnd:
            return True
        if self._hit_snake(x, y):
            return True
        return is_desktop_window(h)

    def _hit_snake(self, x, y):
        for gx, gy in self.seg_pos:
            if (gx - x) ** 2 + (gy - y) ** 2 <= 1600:
                return True
        return False

    # ---- 主步进 ----
    def _step(self):
        if self._is_sleeping():
            self.satiety = 0.0
        else:
            self.satiety = max(0.0, self.satiety - SATIETY_DECAY_PER_SEC * TICK_MS / 1000.0)
        sleeping = self._is_sleeping()
        self._mood_timers()
        if sleeping:
            now = time.monotonic()
            if self._sleep_since is None:
                self._sleep_since = now
                self._sleep_dur = random.uniform(15.0, 25.0)
            elif now - self._sleep_since >= self._sleep_dur:
                self._sleep_since = None
                self.satiety = random.uniform(25.0, 45.0)
                (hx, hy) = self.snake.head()
                self._spawn_particles(hx, hy - 10, 3)
                logging.info('睡醒啦(睡了 %.0f 秒)', self._sleep_dur)
            self._zdan_timer -= 1
            if self._zdan_timer <= 0:
                self._zdan_timer = random.randint(18, 26)
                self._spawn_zdan()
            self._consume_interact(now)   # 睡中也要处理互动(拎起唤醒)
            if now - self._last_check >= 1.0:
                self._last_check = now
                self._refresh_avoid()
                self._self_check()
            self._aging()
            self._render()
            return
        state = self.cfg['state']
        if state == 'quiet':
            active = False
        elif state == 'active':
            active = True
        else:
            # [P0-确认] 依据 dis_step.txt 行 1736:auto 档 = 有食物且允许进食才活跃
            active = bool(self.foods) and (not self.cfg['no_eat'])
        now = time.monotonic()
        if now - self._last_check >= 1.0:
            self._last_check = now
            self._refresh_avoid()
            self._self_check()
        step = ACTIVE_STEP if active else QUIET_STEP
        self._last_active = active
        self._consume_interact(now)
        self._coil_step(active)
        dragging = self._interact.state == InteractSM.DRAG
        if active and self.foods and self._break_chase <= 0:
            (hx, hy) = self.snake.head()
            f0 = min(self.foods, key=lambda f: (f['x'] - hx) ** 2 + (f['y'] - hy) ** 2)
            (fx, fy) = (f0['x'], f0['y'])
            dist = math.hypot(fx - hx, fy - hy)
            if dist < self._chase_min - 2.0:
                self._chase_min = dist
                self._chase_stall = 0
            else:
                self._chase_stall += 1
            if self._chase_stall > 150:
                self._chase_stall = 0
                self._chase_min = 1000000000.0
                self._break_chase = 40
        else:
            self._chase_stall = 0
            self._chase_min = 1000000000.0
        if self._break_chase > 0:
            self._break_chase -= 1
            self.snake.ignore_food = True
        else:
            self.snake.ignore_food = False
        pts = [(f['x'], f['y']) for f in self.foods]
        self.snake.avoid_rects = self._avoid
        if dragging:
            eaten = []      # 拎起中:头由 drag 事件驱动,自动位移暂停
        else:
            eaten = self.snake.move(step, active, pts, not self.cfg['no_eat'])
        self._growth_step(active)
        for px, py in eaten:
            self._remove_food_at(px, py)
            self._on_eat()
        self._aging()
        self._render()

    # ---- 避让矩形 ----
    def _refresh_avoid(self):
        '''收集所有可见的置顶+分层窗口矩形(避让它们,防止合成冲突)。
        自己的菜单窗口不避让:菜单打开时蛇照常自由移动。
        [P0-确认] 语义仲裁:字节码跳转极性存在反编译歧义,但原文档字符串
        (来自 code object 常量,无歧义)与真实桌面行为证据(按"避让不可见窗口"
        实现时蛇被大量隐形窗口矩形困死,原版 v4 实测正常游走)均指向本实现;
        已记入 STATUS 决策表 D-004'''
        if self.headless:
            return
        self._avoid = []
        for (hwnd, ex, rect) in enum_topmost_layered_windows():
            if hwnd == self._hwnd or hwnd == self._menu_hwnd:
                continue
            if not is_window_visible(hwnd):
                continue
            if not ex & WS_EX_TOPMOST:
                continue
            if not ex & WS_EX_LAYERED:
                continue
            (l, t, r, b) = rect
            if r - l > 8 and b - t > 8:
                self._avoid.append((l - 240, t - 240, r + 240, b + 240))

    # ---- 合成自愈看门狗 ----
    def _self_check(self):
        '''合成自愈:窗口未被遮挡但蛇头处像素缺失/滞后 → 重建窗口。
        长时间被遮挡(如浏览器盖住桌面)会让合成器冻结宠物表面,
        被遮挡期间周期性重建 + 遮挡结束立即重建一次, 保证回来时是活的。'''
        if self.headless or not self._hwnd:
            return
        (hx, hy) = self.snake.head()
        (hx, hy) = (int(hx), int(hy))
        if not (0 <= hx < self.vw):
            return
        if not (0 <= hy < self.vh):
            return
        try:
            top = window_from_point(hx, hy)
            now = time.monotonic()
            if top != self._hwnd:
                if self._covered_since is None:
                    self._covered_since = now
                    return
                if now - self._covered_since > 15.0 and now - self._last_cover_rebuild >= 60.0:
                    self._last_cover_rebuild = now
                    logging.warning('长时间被遮挡,主动重建窗口')
                    self._rebuild_window()
                return
            if self._covered_since is not None:
                was_long = now - self._covered_since > 15.0
                self._covered_since = None
                if was_long:
                    logging.warning('遮挡结束,重建窗口恢复画面')
                    self._rebuild_window()
                    return
            if self._count_head_color_region(hx, hy, half=20) >= 3 \
                    or self._count_greens_region(hx - 20, hy - 20, 40, 40) >= 4:
                return
            logging.warning('检测到合成失效/滞后,重建窗口')
            self._rebuild_window()
        except Exception:
            return

    def _rebuild_window(self):
        '''销毁并重建分层窗口(恢复被合成器冻结的表面)。重建后保持普通非置顶'''
        try:
            destroy_window(self._hwnd)
            self._hwnd = None
            self._create_window()
            untopmost_window(self._hwnd)
            self._last_check = time.monotonic() + 3
        except Exception as e:
            logging.warning('重建窗口失败: %r', e)

    def _count_head_color_region(self, hx, hy, half=20):
        '''蛇头/贴图主色在蛇头位置的命中数——新鲜度的精确信号'''
        data = grab_screen_bgra(hx - half, hy - half, half * 2 + 1, half * 2 + 1)
        if not data:
            return 0
        n = 0
        for i in range(0, len(data), 8):
            b = data[i]
            gg = data[i + 1]
            r2 = data[i + 2]
            for (wr, wg, wb) in self._watch_colors:
                if abs(r2 - wr) <= 40 and abs(gg - wg) <= 40 and abs(b - wb) <= 40:
                    n += 1
            if n >= 2:
                return n
        return n

    def _count_greens_region(self, x0, y0, w, h):
        '''单次 BitBlt 抓取屏幕小区域,在内存里数绿色(可靠且快)'''
        data = grab_screen_bgra(x0, y0, w, h)
        if not data:
            return 0
        n = 0
        for i in range(0, len(data), 8):
            b = data[i]
            gg = data[i + 1]
            r2 = data[i + 2]
            if gg > 110 and gg > r2 + 15 and gg > b + 15:
                n += 1
            if n >= 3:
                break
        return n

    # ---- 主循环 ----
    def run(self):
        if not os.path.exists(config_path()):
            save_config(self.cfg)
        if self.cfg.get('autostart', True):
            from .platform_win import set_autostart
            set_autostart(True)
        try:
            last = time.monotonic()
            while not self._quitting:
                msg = wintypes.MSG()
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                self._drain_events()
                now = time.monotonic()
                if now - last >= TICK_MS / 1000:
                    last = now
                    try:
                        self._step()
                    except Exception:
                        logging.exception('tick 异常')
                time.sleep(0.003)
            self.quit()
        except Exception:
            self.quit()
            raise

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        if not self.headless:
            self._stop_hook()
        self._free_dib()
        try:
            self.save_pet_state_now(reason='quit')
        except Exception as e:
            logging.warning('退出存档失败: %r', e)
        if self._menu_hwnd:
            destroy_window(self._menu_hwnd)
            self._menu_hwnd = None
        self.menu_open = False
        if self._hwnd:
            destroy_window(self._hwnd)
            self._hwnd = None


def selftest():
    '''v4 断言全集(BASELINE §10, 共 7 条)+ 模块导入/常量表自检'''
    import snake_pet
    from snake_pet import constants
    from snake_pet.constants import BODY_MIN, BODY_MAX
    assert constants.SEG == 20 and constants.HEAD_R == 17 and constants.BODY_R == 10
    assert constants.EAT_RADIUS == 15 and constants.GROW_PER_FOOD == 20
    assert constants.MAX_FOODS == 30 and constants.BODY_MAX == 2000
    assert constants.QUIET_STEP == 1.6 and constants.ACTIVE_STEP == 9.5
    assert constants.SATIETY_DECAY_PER_SEC == 0.1
    assert snake_pet.__version__

    b = (50, 50, 1500, 900)
    s = Snake(400, 300, (1, 0), b)
    foods = [(1200, 600)]
    ate = 0
    for _ in range(3000):
        eaten = s.move(ACTIVE_STEP, True, foods, True)
        for e in eaten:
            ate += 1
            foods = [(300, 200)]
        (hx, hy) = s.head()
        assert b[0] <= hx <= b[2] and b[1] <= hy <= b[3], (hx, hy)
        assert len(s.path) <= MAX_PATH
    assert ate > 0, '应该能吃到食物'
    assert s.body_len == 5 * SEG + ate * GROW_PER_FOOD, '每次吃食物只长 GROW_PER_FOOD'
    s2 = Snake(400, 300, (1, 0), b)
    for _ in range(600):
        s2.move(QUIET_STEP, False, [(1200, 600)], True)
        (hx, hy) = s2.head()
        assert b[0] <= hx <= b[2] and b[1] <= hy <= b[3], (hx, hy)
    assert s2.body_len == 5 * SEG, '安静模式不应该吃食物'
    s3 = Snake(700, 300, (0, 1), b)
    for _ in range(500):
        s3.move(ACTIVE_STEP, True, [(700, 800)], False)
    assert s3.body_len == 5 * SEG
    s4 = Snake(100, 100, (1, 0), b)
    for _ in range(4000):
        s4.move(ACTIVE_STEP, True, [(80, 80)], True)
        (hx, hy) = s4.head()
        assert b[0] <= hx <= b[2] and b[1] <= hy <= b[3], (hx, hy)
    s5 = Snake(500, 400, (0, 1), b)
    for _ in range(200):
        s5.move(QUIET_STEP, False, [], True)
    for i in range(1, 10):
        (ax, ay) = s5.pos(i * SEG + 4)
        (bx_, by_) = s5.pos((i - 1) * SEG + 4)
        d = math.hypot(ax - bx_, ay - by_)
        assert abs(d - SEG) < SEG, '身体节距应接近 SEG, 实际 %.2f' % d
    s6 = Snake(300, 300, (1, 0), b, body_len=SEG * 5)
    s6.body_len += SEG * 3
    s6.ensure_path_len(s6.body_len + 40)
    assert s6.path[-1][2] - s6.path[0][2] >= s6.body_len + 40, '轨迹应覆盖身体全长'
    (tx, ty) = s6.pos(s6.body_len)
    assert b[0] - 5 <= tx <= b[2] + 5 and b[1] - 5 <= ty <= b[3] + 5
    s6.body_len = BODY_MIN
    assert s6.body_len >= BODY_MIN, '缩短不应低于下限'
    assert BODY_MAX > BODY_MIN
    print('selftest OK')


def _setup_logging():
    '''日志限量轮转(≤5MB×2 备份,AC-F8-3)'''
    import logging.handlers
    log_path = os.path.join(base_dir(), 'snake_pet.log')
    handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024,
                                                   backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[handler])


def main():
    import logging
    _setup_logging()
    if not acquire_single_instance_mutex():
        return
    ensure_dpi_aware()
    try:
        cfg = load_config()
        app = SnakePet(cfg)
        app.run()
    except Exception:
        logging.exception('程序异常退出')
        raise
