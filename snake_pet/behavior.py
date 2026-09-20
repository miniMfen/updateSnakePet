'''行为状态机 —— 饱食度/心情/睡觉/空闲小动作/进食反应/夜间判定/分层盘旋(P2)。'''
import logging
import math
import random
import time

from .constants import (MAX_FOODS, MOOD_HAPPY, MOOD_HUNGRY, FX_COLORS, SATIETY_GAIN,
                        SATIETY_MAX, SLEEP_COIL_ATTEMPTS, SLEEP_COIL_RETRY_MS,
                        SLEEP_COOLDOWN_RANGE, SLEEP_DUR_RANGE, TICK_MS)
from .growth import stage_of


class BehaviorMixin:
    def _is_sleeping(self):
        '''饱食度归零 = 想睡(饿到极限)。**语义与 v5.1 保持一致**,既有测试依赖它。'''
        return self.satiety <= 0

    def _is_dozing(self):
        '''v5.2:是否正在打呼噜。复用 _sleep_since 的非空语义 —— v5.2 之前它就是
        「已进入睡眠计时」的标志(渲染探针也用它伪造睡眠场景),因此保持这条等价关系
        既让探针无需改动,也让「想睡」与「正在睡」两个概念彻底分开。'''
        return self._sleep_since is not None

    def _mood(self):
        if self._is_dozing():
            return 'sleep'
        if self.satiety >= MOOD_HAPPY:
            return 'happy'
        if self.satiety >= MOOD_HUNGRY:
            return 'normal'
        return 'hungry'      # v5.2:satiety==0 但还没睡着(含入睡前盘旋) → 睁眼显示饿,不再直接闭眼

    def _wake(self):
        self._sleep_phase = None
        self._sleep_since = None
        self._coil_started = False
        self._sleep_cooldown_until = time.monotonic() + random.uniform(*SLEEP_COOLDOWN_RANGE)
        self.satiety = max(self.satiety, 15)
        (hx, hy) = self.snake.head()
        self._spawn_particles(hx, hy - 10, 3)

    # ---- v5.2 睡觉三阶段状态机(需求1) ----
    def _sleep_step(self, now):
        '''空闲 → 盘旋准备('coiling') → 打呼噜('dozing') → 冷却。
        返回 True 表示正在打呼噜,调用方应跳过运动/进食。

        用户诉求:睡觉前必须先盘旋;睡 6~12s(从盘旋结束计时);别太频繁。
        盘旋起不来时不空转 —— 重试 SLEEP_COIL_ATTEMPTS 次后降级为直接入睡(记日志)。
        '''
        # 0) 盘旋准备期吃到东西 → 放弃这次入睡(吃东西自然会醒)
        if self._sleep_phase == 'coiling' and not self._is_sleeping():
            if self.snake.coil is not None:
                self.snake.coil.fast_unwind()
            logging.info('吃东西了,不睡了(取消入睡前盘旋)')
            self._sleep_phase = None

        # 1) 饿了 且 冷却已过 → 进入盘旋准备
        if self._sleep_phase is None and self._is_sleeping() and now >= self._sleep_cooldown_until:
            self._sleep_phase = 'coiling'
            self._coil_started = False
            self._coil_attempts = 0
            self._coil_retry_at = 0.0
            self._coil_began = 0.0
            logging.info('困了:先盘旋再睡')

        # 2) 盘旋准备
        if self._sleep_phase == 'coiling':
            if self._coil_started:
                if self.snake.coil is None:       # 盘完(自然结束或快速盘出)
                    self._begin_doze(now)
            elif now >= self._coil_retry_at:
                self._coil_retry_at = now + SLEEP_COIL_RETRY_MS / 1000.0
                self._coil_attempts += 1
                self._start_coil()
                self._coil_started = self.snake.coil is not None
                if self._coil_started:
                    self._coil_began = now
                elif self._coil_attempts >= SLEEP_COIL_ATTEMPTS:
                    logging.info('盘旋起不来(尝试 %d 次),降级为直接入睡', self._coil_attempts)
                    self._begin_doze(now)

        # 3) 打呼噜
        if self._sleep_phase == 'dozing':
            if self._sleep_since is None:
                self._sleep_since = now
            if now - self._sleep_since >= self._sleep_dur:
                self._end_doze(now)
            else:
                return True
        return False

    def _begin_doze(self, now):
        '''盘旋结束 → 开始打呼噜。睡长在此刻抽取(6~12s 随机)。'''
        self._sleep_phase = 'dozing'
        self._sleep_since = now
        self._sleep_dur = random.uniform(*SLEEP_DUR_RANGE)
        self.snake.coil = None
        self._zdan_timer = 0                      # 立刻起第一发 Z 弹幕
        coil_sec = (now - self._coil_began) if self._coil_began else 0.0
        logging.info('盘旋 %.1fs 结束 → 开始打呼噜,睡 %.1fs', coil_sec, self._sleep_dur)

    def _end_doze(self, now):
        '''睡醒:抬高饱食度 + 设冷却,避免立刻又想睡。'''
        self._sleep_phase = None
        self._sleep_since = None
        self._coil_started = False
        self._sleep_cooldown_until = now + random.uniform(*SLEEP_COOLDOWN_RANGE)
        self.satiety = random.uniform(25.0, 45.0)
        (hx, hy) = self.snake.head()
        self._spawn_particles(hx, hy - 10, 3)
        logging.info('睡醒啦(睡了 %.1f 秒),冷却 %.1f 秒后才可能再困',
                     self._sleep_dur, self._sleep_cooldown_until - now)

    def _mood_timers(self):
        # [P0-确认] 依据字节码 `_mood_timers`:仅当 无食物/未盘旋/未睡觉 时倒计时,
        # 计时到 0 先复位再触发一次空闲小动作(修复版把条件写反且每帧调用,已纠正)
        mood = self._mood()
        if not self.foods and self.snake.coil is None and mood != 'sleep':
            self._idle_timer -= 1
            if self._idle_timer <= 0:
                self._idle_timer = random.randint(600, 1200)
                self._do_idle()
        if mood == 'happy':
            self._heart_timer -= 1
            if self._heart_timer <= 0:
                self._heart_timer = random.randint(180, 420)
                (hx, hy) = self.snake.head()
                self._spawn_fx('heart', hx, hy - 14, size=random.uniform(4, 6),
                               color=random.choice(FX_COLORS), max=random.randint(36, 50),
                               seed=random.random())
                return
        if mood == 'hungry':
            self._hungry_timer -= 1
            if self._hungry_timer <= 0:
                self._hungry_timer = random.randint(360, 660)
                self._spawn_bubble('我饿了～')
                return
        if mood == 'sleep':
            self._zzz_timer -= 1
            if self._zzz_timer <= 0:
                self._zzz_timer = random.randint(240, 480)
                (hx, hy) = self.snake.head()
                self._spawn_fx('zzz', hx, hy - 16, max=48)

    def _do_idle(self):
        '''空闲小动作(无食物且非睡,每 600~1200 帧触发):吐泡泡/歪头/分层盘旋。
        盘旋权重 2/4:它是 v5 招牌行为(用户点名),且仅在真正空闲时发生'''
        if self._sleep_phase is not None:
            return                     # v5.2:入睡流程进行中(盘旋准备期),不再插入其它空闲动作
        act = random.choice(('bubble', 'tilt', 'coil', 'coil'))
        (hx, hy) = self.snake.head()
        if act == 'bubble':
            (ux, uy) = self.snake.heading()
            self._spawn_fx('bfx', hx + ux * 10, hy + uy * 10,
                           size=random.uniform(4, 6), max=40)
            return
        if act == 'tilt':
            self.tilt = 12
            return
        self._start_coil()

    # ---- 分层盘旋(P2) ----
    def _start_coil(self):
        '''触发盘旋:打呼噜中/摆尾动画中/已在盘旋 → 忽略;空间不足由 make_coil_plan 取消。
        v5.2:守卫由 _is_sleeping() 改为 _is_dozing() —— 否则「入睡前盘旋准备」会被自己拦住
        (准备期 satiety 仍为 0,但此时蛇是清醒的,必须允许起盘)。'''
        if self._is_dozing() or self.wag > 0 or self.snake.coil is not None:
            return
        plan = self.snake.make_coil_plan()
        if plan is None:
            logging.info('盘旋取消:空间不足或体长过短')
            return
        self.snake.coil = plan
        self._ach.counters['coil_count'] = self._ach.counters.get('coil_count', 0) + 1
        self._unlock_achievements()
        (hx, hy) = self.snake.head()
        for _ in range(4):
            self._spawn_fx('star', hx + random.uniform(-24, 24), hy + random.uniform(-26, -2),
                           size=random.uniform(3, 5), color=random.choice(FX_COLORS),
                           max=30, seed=random.random())

    def _coil_step(self, active):
        '''每帧盘旋伴生逻辑:盘踞冒泡泡、食物+活跃档快速盘出、结束庆祝'''
        plan = self.snake.coil
        if plan is None:
            return
        if plan.in_out_phase and plan.t % 24 == 0:
            (hx, hy) = self.snake.head()
            self._spawn_fx('bfx', hx, hy - 12, size=random.uniform(3, 5), max=36)
        if active and self.foods and not plan.in_out_phase:
            plan.fast_unwind()   # AC-F2-4:优雅中断,快速盘出
        if plan.finished and not plan.celebrated:
            plan.celebrated = True
            self.wag = 14
            (hx, hy) = self.snake.head()
            for _ in range(3):
                self._spawn_fx('star', hx + random.uniform(-22, 22), hy + random.uniform(-26, -2),
                               size=random.uniform(3, 5), color=random.choice(FX_COLORS),
                               max=30, seed=random.random())

    def _on_eat(self):
        self.satiety = min(SATIETY_MAX, self.satiety + SATIETY_GAIN)
        self.flash = 2
        self.wag = 14
        (hx, hy) = self.snake.head()
        self._spawn_particles(hx, hy - 6, random.randint(3, 5))
        # P6 养成计数与成就
        self._ach.counters['total_eaten'] = self._ach.counters.get('total_eaten', 0) + 1
        self._eat_times.append(time.monotonic())
        self._unlock_achievements()
        if self._ach.counters.get('stage_seen') != stage_of(self._ach.counters['total_eaten']):
            self._ach.counters['stage_seen'] = stage_of(self._ach.counters['total_eaten'])
            self.save_pet_state_now(reason='stage')

    def _spawn_zdan(self):
        '''睡觉 Z 弹幕:一条大 Z 从蛇头旁横向飘过画面(弹幕式)'''
        (hx, hy) = self.snake.head()
        direction = random.choice((-1, 1))
        start_x = hx + direction * random.uniform(70, 150)
        self._spawn_fx('zdan', start_x, hy + random.uniform(-70, 40),
                       vx=direction * random.uniform(1.2, 2.2), vy=random.uniform(-0.15, 0.15),
                       size=random.uniform(26, 42), max=random.randint(70, 110),
                       seed=random.random())

    def _on_double_click(self, lx, ly):
        '''双击蛇头:弹出随机文字气泡(容忍表面滞后,70px 内都算头)'''
        (hx, hy) = self.snake.head()
        if math.hypot(lx - hx, ly - hy) > 70:
            self.hop = 8
            return False
        mood = self._mood()
        if mood == 'sleep':
            txt = '呼噜…'
        elif mood == 'hungry':
            txt = '饿饿～'
        elif mood == 'happy':
            txt = random.choice(('嘿！', '今天也要加油呀！', '陪我玩嘛～'))
        else:
            txt = random.choice(('嗯？', '早安～', '嘿嘿'))
        self._spawn_bubble(txt)
        return True

    def _do_moe(self):
        '''卖萌:歪头+摆尾+爱心+气泡,肉眼可见的连续小动作'''
        self.tilt = 14
        self.wag = 20
        (hx, hy) = self.snake.head()
        for _ in range(3):
            self._spawn_fx('heart', hx + random.uniform(-18, 18), (hy - 8) + random.uniform(-14, 2),
                           size=random.uniform(4, 7), color=random.choice(FX_COLORS),
                           max=random.randint(36, 50), seed=random.random())
        self._spawn_bubble('我最可爱～')

    def _spawn_food(self, x, y):
        x = min(max(x, 12), self.vw - 12)
        y = min(max(y, 12), self.vh - 12)
        if len(self.foods) >= MAX_FOODS:
            self.foods.pop(0)
        self.foods.append({'x': x, 'y': y})
        self._ach.counters['total_feed'] = self._ach.counters.get('total_feed', 0) + 1
        self._unlock_achievements()
        if self._is_sleeping():
            self._wake()

    def _feed_one(self):
        '''投喂(P5):头前方 150~300px、heading±40° 随机;受 MAX_FOODS 约束'''
        if len(self.foods) >= MAX_FOODS:
            self._spawn_bubble('吃不下了~')
            return
        (hx, hy) = self.snake.head()
        (x0, y0, x1, y1) = self.bounds
        (fx, fy) = (hx, hy)
        for _ in range(8):
            ang = self.snake.heading_angle + random.uniform(-math.radians(40), math.radians(40))
            dist = random.uniform(150, 300)
            fx = min(max(hx + math.cos(ang) * dist, x0), x1)
            fy = min(max(hy + math.sin(ang) * dist, y0), y1)
            ok = all(not (ax0 <= fx <= ax1 and ay0 <= fy <= ay1)
                     for (ax0, ay0, ax1, ay1) in self._avoid)
            if ok:
                break
        self._spawn_food(fx, fy)
        self._spawn_bubble('开饭啦~')

    def _remove_food_at(self, x, y):
        '''吃掉坐标处的食物;同一位置堆叠的多份食物一次性全部移除'''
        keep = []
        removed = False
        for f in self.foods:
            if abs(f['x'] - x) < 0.5 and abs(f['y'] - y) < 0.5:
                if not removed:
                    self.effects.append({'t': 0, 'x': x, 'y': y})
                    removed = True
                continue
            keep.append(f)
        self.foods = keep

    def _is_night(self):
        '''22:00 ~ 6:00 为夜间(帽子 auto 档夜间戴夜帽)'''
        hour = time.localtime().tm_hour
        return hour >= 22 or hour < 6
