'''v5.2 BUG-A 回归测试：档位只影响步速，不再否决进食。

用户反馈(2026-09-21)：菜单里「不再吃食物」是**关**的，蛇却怎么也不来吃桌面上的苹果。
根因：`state == 'quiet'`（安静档）在 app 层把 active 压成 False，而"追食 + 进食"两个
判定都挂在 active 上（`snake.move` 里 `if active and eat_enabled`），于是安静档
**连碰到食物都不吃** —— 食物永远吃不到 → 饱食度掉到 0 → 进入"盘旋→睡→醒→冷却"死循环。
该语义来自 v4 原始设计（commit cf71fe7），并非近期改动。

修复：把"要不要去吃"从 active 解耦，由 `want_eat = 有食物 and 未禁食` 决定；
      安静档保持安静步速，但照样去吃（用户 2026-09-21 拍板："安静档也去吃（慢速）"）。

注意：`Snake.move(step, active, foods, eat_enabled)` 的既有语义**没有变**
（新增的 chase 参数默认跟随 active），因此 `tests/test_snake.py` 的既有断言无需改动。
'''
import random

import pytest

from snake_pet.app import SnakePet
from snake_pet.config import load_config
from snake_pet.constants import ACTIVE_STEP, QUIET_STEP, SEG
from snake_pet.snake import Snake

B = (50, 50, 1500, 900)


@pytest.fixture(autouse=True)
def _seed():
    random.seed(7)


def _app(state, no_eat=False, seed=7):
    random.seed(seed)
    cfg = load_config()
    cfg.update(autostart=False, autosave=False, no_eat=no_eat, state=state, no_spawn=True)
    app = SnakePet(cfg, headless=True)
    (bx0, by0, bx1, by1) = app.bounds
    (hx, hy) = app.snake.head()
    fx = min(hx + 120.0, bx1 - 30.0)
    fy = min(max(hy, by0 + 30.0), by1 - 30.0)
    app.foods = [{'x': fx, 'y': fy}]
    return app


def _drive(app, frames=400):
    '''推进若干帧，返回 (是否吃到过东西, 单帧最大头部位移)'''
    start_len = app.snake.body_len
    max_step = 0.0
    for _ in range(frames):
        (px, py) = app.snake.head()
        app._step_impl()
        (cx, cy) = app.snake.head()
        max_step = max(max_step, ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5)
    return app.snake.body_len > start_len + 1e-6, max_step


# ---------------------------------------------------------------- 应用层契约

def test_quiet_mode_still_eats():
    '''安静档 + 未禁食 → 必须去吃（本次修复的核心断言）'''
    app = _app('quiet')
    ate, _ = _drive(app)
    assert ate, '安静档应当去吃食物（修复前这里是 False：安静档完全不进食）'


def test_quiet_mode_eats_at_quiet_speed():
    '''安静档去吃时仍走安静步速，不切换成活跃步速'''
    app = _app('quiet')
    _, max_step = _drive(app, frames=250)
    assert max_step <= QUIET_STEP + 1e-6, '安静档追食不应跑出活跃步速(%.3f)' % max_step


def test_quiet_mode_respects_no_eat_switch():
    '''真正打开「不再吃食物」时，安静档也不吃（开关仍是唯一的禁食入口）'''
    app = _app('quiet', no_eat=True)
    ate, _ = _drive(app)
    assert not ate, '关闭进食开关后不应吃到食物'


def test_auto_mode_still_eats():
    app = _app('auto')
    ate, _ = _drive(app)
    assert ate


def test_active_mode_eats_at_active_speed():
    app = _app('active')
    ate, max_step = _drive(app, frames=250)
    assert ate
    assert max_step <= ACTIVE_STEP + 1e-6


# ---------------------------------------------------------------- snake 层兼容

def test_snake_level_default_chase_matches_active():
    '''不传 chase 时语义与改动前一致（active=False 不吃）—— 既有测试因此无需改动'''
    s = Snake(400, 300, (1, 0), B)
    for _ in range(600):
        s.move(QUIET_STEP, False, [(1200, 600)], True)
    assert s.body_len == 5 * SEG


def test_snake_level_chase_true_allows_slow_eating():
    '''显式 chase=True + active=False：慢速也能吃到'''
    s = Snake(400, 300, (1, 0), B)
    ate = False
    for _ in range(3000):
        eaten = s.move(QUIET_STEP, False, [(1200, 600)], True, chase=True)
        if eaten:
            ate = True
            break
    assert ate


def test_snake_level_chase_false_blocks_eating_even_when_active():
    '''chase=False 时即便 active=True 也不进食（参数语义可独立控制）'''
    s = Snake(700, 300, (0, 1), B)
    for _ in range(500):
        s.move(ACTIVE_STEP, True, [(700, 800)], True, chase=False)
    assert s.body_len == 5 * SEG
