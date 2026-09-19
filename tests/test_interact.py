'''P5 互动测试 —— 状态机(T10)/拎起节距/冲突矩阵/睡中拎起唤醒/投喂'''
import math
import random

import pytest

from snake_pet.app import SnakePet
from snake_pet.config import load_config
from snake_pet.constants import HEAD_R, MAX_FOODS, QUIET_STEP, SEG
from snake_pet.interact import InteractSM


def test_petting_flow_t10():
    # press→持住 0.4s→release ⇒ PETTING 完成,affinity+1;冷却期内重复不触发
    sm = InteractSM((0, 0, 1000, 800))
    sm.press(500, 400, True, now=10.0)
    assert sm.state == InteractSM.PRESS_HEAD
    sm.move(503, 402, now=10.4)          # 位移 3.6px ≤8,持住 0.4s ≥0.3s
    assert sm.state == InteractSM.PETTING
    evs = sm.take_events()
    assert ('pet_start', 503.0, 402.0) in evs
    sm.release(503, 402, now=10.7)
    evs = sm.take_events()
    assert evs and evs[0][0] == 'pet_done'
    assert sm.affinity == 1
    # 冷却期内再按不触发
    sm.press(500, 400, True, now=11.0)
    sm.move(502, 401, now=11.4)
    assert sm.state != InteractSM.PETTING
    sm.release(502, 401, now=11.5)
    assert sm.affinity == 1
    # 冷却结束后可再抚摸
    sm.press(500, 400, True, now=13.0)
    sm.move(502, 401, now=13.4)
    assert sm.state == InteractSM.PETTING
    sm.release(502, 401, now=13.6)
    assert sm.affinity == 2


def test_petting_auto_complete():
    # 持住超过 0.3+1.2s → tick 自动完成
    sm = InteractSM((0, 0, 1000, 800))
    sm.press(500, 400, True, now=0.0)
    sm.move(501, 401, now=0.35)          # 进入 PETTING
    assert sm.state == InteractSM.PETTING
    sm.tick(1.6)
    assert sm.affinity == 1
    assert sm.state == InteractSM.IDLE


def test_drag_flow_t10():
    # press→move 50px→release ⇒ drag_start/drag/drop;cursor clamp 在 bounds
    sm = InteractSM((0, 0, 1000, 800))
    sm.press(800, 700, True, now=0.0)
    sm.move(860, 760, now=0.1)
    assert sm.state == InteractSM.DRAG
    sm.move(1200, 900, now=0.2)          # 超界 move
    sm.release(1200, 900, now=0.3)
    kinds = [e[0] for e in sm.take_events()]
    assert 'drag_start' in kinds and 'drag' in kinds and 'drop' in kinds


def test_short_press_no_action():
    # 蛇身/头部短按无位移 → 无任何动作(防误触)
    sm = InteractSM((0, 0, 1000, 800))
    sm.press(500, 400, True, now=0.0)
    sm.release(500, 400, now=0.1)
    assert sm.take_events() == []
    assert sm.affinity == 0


def _headless_app(seed=21):
    random.seed(seed)
    cfg = load_config()
    cfg['autostart'] = False
    return SnakePet(cfg, headless=True)


def test_drag_keeps_segment_spacing():
    # 拎起:头单帧位移受限(≤DRAG_MAX_STEP),身体采样沿弧长连续(无撕裂),终点 clamp 在 bounds
    import time as _time
    from snake_pet.interact import DRAG_MAX_STEP
    app = _headless_app()
    for _ in range(60):
        app.snake.move(QUIET_STEP, False, [], True)
    (hx, hy) = app.snake.head()
    t_now = _time.monotonic()
    app._interact.press(hx + app.vx, hy + app.vy, True, now=t_now)
    path = [(hx, hy)]
    for i in range(30):
        t_now += 0.016
        nx = hx + 25 + i * 6
        ny = hy + 10 + i * 3
        app._interact.move(nx, ny, now=t_now)
        app._consume_interact(t_now)
        app._step()
        (px, py) = app.snake.head()
        path.append((px, py))
        d = math.hypot(px - path[-2][0], py - path[-2][1])
        assert d <= DRAG_MAX_STEP + 1.0, d
        # 弧长连续:相邻身体采样点的欧氏距离不超过弧长间距(急转角允许收缩)
        (ax, ay) = app.snake.pos(2 * SEG)
        (bx_, by_) = app.snake.pos(SEG)
        seg_d = math.hypot(ax - bx_, ay - by_)
        assert seg_d <= SEG + 2.0, seg_d
    (bx0, by0, bx1, by1) = app.bounds
    (px, py) = app.snake.head()
    assert bx0 - 1 <= px <= bx1 + 1 and by0 - 1 <= py <= by1 + 1
    app.quit()


def test_drag_wakes_sleeping_snake():
    app = _headless_app()
    app.satiety = 0.0
    assert app._is_sleeping()
    (hx, hy) = app.snake.head()
    app._interact.press(hx + app.vx, hy + app.vy, True, now=0.0)
    app._interact.move(hx + app.vx + 60, hy + app.vy, now=0.1)
    app._consume_interact(0.1)
    assert not app._is_sleeping()
    assert app.satiety >= 15
    app.quit()


def test_conflict_matrix_desktop_spawn_unaffected():
    # 桌面 press 撒食不受互动状态机影响
    app = _headless_app()
    app.cfg['no_spawn'] = False
    app._interact.press(100 + app.vx, 100 + app.vy, False, now=0.0)
    n = len(app.foods)
    app._spawn_food(100, 100)
    assert len(app.foods) == n + 1
    app.quit()


def test_conflict_matrix_double_click_priority():
    # 双击优先:0.45s 内二次按下 → hop+气泡,且不进入抚摸/拎起
    app = _headless_app()
    for _ in range(60):
        app.snake.move(QUIET_STEP, False, [], True)
    app._render_frame()                  # 填充 seg_pos 命中数据
    (hx, hy) = app.snake.head()
    app.evq.put(('L', hx + app.vx, hy + app.vy))
    app._drain_events()
    app.evq.put(('L', hx + app.vx + 3, hy + app.vy))
    app._drain_events()
    assert app.hop == 8
    assert app._interact.state == InteractSM.IDLE
    assert any(fx['type'] == 'text' for fx in app.fx), '双击应有气泡'
    app.quit()


def test_conflict_matrix_right_click_menu():
    # 右键菜单不受影响
    app = _headless_app()
    for _ in range(60):
        app.snake.move(QUIET_STEP, False, [], True)
    app._render_frame()                  # 填充 seg_pos 命中数据
    (hx, hy) = app.snake.head()
    app.evq.put(('R', hx + app.vx, hy + app.vy))
    app._drain_events()
    assert app.menu_open
    app.quit()


def test_feed_one_places_food():
    # 投喂:头前方 150~300px 处生成食物;满仓时气泡且不增加
    app = _headless_app()
    app.foods = []
    n0 = len(app.foods)
    app._feed_one()
    assert len(app.foods) == n0 + 1
    (fx, fy) = (app.foods[-1]['x'], app.foods[-1]['y'])
    (hx, hy) = app.snake.head()
    d = math.hypot(fx - hx, fy - hy)
    assert 140 <= d <= 320, d
    app.foods = [{'x': 0, 'y': 0} for _ in range(MAX_FOODS)]
    app._feed_one()
    assert len(app.foods) == MAX_FOODS
    assert any(f.get('text') == '吃不下了~' for f in app.fx)
    app.quit()
