'''行为状态机 —— 饱食度/心情/睡觉/空闲小动作/进食反应/夜间判定(v4 语义,
含 P0 字节码仲裁修正:空闲动作计时、睡帽菜单赋值等)。'''
import math
import random
import time

from .constants import (MAX_FOODS, MOOD_HAPPY, MOOD_HUNGRY, FX_COLORS, SATIETY_GAIN,
                        SATIETY_MAX)


class BehaviorMixin:
    def _is_sleeping(self):
        return self.satiety <= 0

    def _mood(self):
        if self.satiety >= MOOD_HAPPY:
            return 'happy'
        if self.satiety >= MOOD_HUNGRY:
            return 'normal'
        if self.satiety > 0:
            return 'hungry'
        return 'sleep'

    def _wake(self):
        self._sleep_since = None
        self.satiety = max(self.satiety, 15)
        (hx, hy) = self.snake.head()
        self._spawn_particles(hx, hy - 10, 3)

    def _mood_timers(self):
        # [P0-确认] 依据字节码 `_mood_timers`:仅当 无食物/未盘旋/未睡觉 时倒计时,
        # 计时到 0 先复位再触发一次空闲小动作(修复版把条件写反且每帧调用,已纠正)
        mood = self._mood()
        if not self.foods and self._spin <= 0 and mood != 'sleep':
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
        '''空闲小动作(无食物且非睡,每 600~1200 帧三选一):吐泡泡/歪头/原地打转'''
        act = random.choice(('bubble', 'tilt', 'spin'))
        (hx, hy) = self.snake.head()
        if act == 'bubble':
            (ux, uy) = self.snake.heading()
            self._spawn_fx('bfx', hx + ux * 10, hy + uy * 10,
                           size=random.uniform(4, 6), max=40)
            return
        if act == 'tilt':
            self.tilt = 12
            return
        self._spin = 36
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
        if self._is_sleeping():
            self._wake()

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
        '''22:00 ~ 6:00 为夜间(戴睡帽);菜单可强制 戴上/摘掉'''
        if self._hat_override is not None:
            return self._hat_override
        hour = time.localtime().tm_hour
        return hour >= 22 or hour < 6
