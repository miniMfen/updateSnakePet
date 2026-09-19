'''特效定义与粒子(spawn/老化回收,防内存泄漏)。
作为 mixin 挂到 SnakePet 上,保持 v4 方法名与 self 访问方式不变。'''
import math
import random

from .constants import FX_COLORS, FX_MAX, TONGUE_FRAMES, TONGUE_PERIOD


class FxMixin:
    def _spawn_fx(self, kind, x, y, **kw):
        fx = {
            'type': kind,
            'x': x,
            'y': y,
            't': 0,
            'max': 45,
        }
        fx.update(kw)
        self.fx.append(fx)
        if len(self.fx) > FX_MAX:
            self.fx.pop(0)

    def _spawn_particles(self, x, y, n=4):
        '''进食/唤醒时的彩色小星星/爱心粒子,向上飘散'''
        for _ in range(n):
            kind = random.choice(('star', 'heart'))
            ang = random.uniform(-math.pi * 0.85, 0)
            sp = random.uniform(1, 2.6)
            self._spawn_fx(kind, x, y, vx=math.cos(ang) * sp, vy=math.sin(ang) * sp,
                           size=random.uniform(4, 7), color=random.choice(FX_COLORS),
                           max=random.randint(36, 52), seed=random.random())

    def _spawn_bubble(self, text):
        (hx, hy) = self.snake.head()
        self._spawn_fx('text', hx, hy - 42, text=text, max=80, size=4)

    def _aging(self):
        '''所有临时特效与状态帧的老化回收(防内存泄漏)'''
        alive = []
        for fx in self.fx:
            fx['t'] += 1
            if fx['type'] in ('heart', 'star', 'foam', 'zdan'):
                fx['x'] += fx.get('vx', 0)
                fx['y'] += fx.get('vy', 0)
            if fx['t'] < fx['max']:
                alive.append(fx)
        self.fx = alive
        if self.hop > 0:
            self.hop -= 1
        if self.flash > 0:
            self.flash -= 1
        if self.wag > 0:
            self.wag -= 1
        if self.tilt > 0:
            self.tilt -= 1
        # P3 吐信计时:每 4~7s 弹出 8 帧(睡觉时不吐)
        if self.tongue > 0:
            self.tongue -= 1
        else:
            self._tongue_timer -= 1
            if self._tongue_timer <= 0:
                self._tongue_timer = random.randint(*TONGUE_PERIOD)
                if not self._is_sleeping():
                    self.tongue = TONGUE_FRAMES
        alive = []
        for e in self.effects:
            e['t'] += 1
            if e['t'] <= 14:
                alive.append(e)
        self.effects = alive
