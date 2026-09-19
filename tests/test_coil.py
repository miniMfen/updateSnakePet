'''P2 分层盘旋测试 —— 几何(T05)/边界(T06)/中断/短蛇降级'''
import math
import random

import pytest

from snake_pet.app import SnakePet
from snake_pet.config import load_config
from snake_pet.constants import ACTIVE_STEP, BODY_R, QUIET_STEP, SEG
from snake_pet.snake import Snake

B = (50, 50, 1500, 900)


def _wrap_pi(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _make(seed, body_segs=60, bounds=B, pos=(700, 500), heading=0.0):
    random.seed(seed)
    return Snake(pos[0], pos[1], heading, bounds, body_len=SEG * body_segs)


def test_coil_plan_feasible_and_layered():
    s = _make(123, body_segs=60)
    plan = s.make_coil_plan()
    assert plan is not None
    assert not plan.small
    # 圈距公式独立复算:相邻同向圈径向差 ≥ 1.6×BODY_R(AC-F2-2)
    gap = (plan.r0 - plan.r_min) / plan.revs
    assert gap >= 1.6 * BODY_R, gap
    assert plan.revs >= 2  # 体长 60 节 ≥ 40 节 → 至少 2 层


def test_coil_geometry_t05():
    # 完整三阶段:盘入半径单调不增、终值=r_min、θ 连续
    s = _make(123, body_segs=60)
    plan = s.make_coil_plan()
    assert plan is not None
    s.coil = plan
    rs_plan = [plan.radius_at(t) for t in range(plan.t_in + 1)]
    for i in range(len(rs_plan) - 1):
        assert rs_plan[i + 1] <= rs_plan[i] + 1e-9, '盘入段半径应单调不增'
    assert abs(plan.radius_at(plan.t_in) - plan.r_min) < 1e-6  # 盘入结束精确到 r_min
    # 实际头轨迹跟踪
    rows = []
    for i in range(plan.t_in + 30):
        (hx, hy) = s.head()
        r = math.hypot(hx - plan.cx, hy - plan.cy)
        th = math.atan2(hy - plan.cy, hx - plan.cx)
        rows.append((r, th))
        s.move(ACTIVE_STEP, False, [], True)
    # 前 12 帧为起步瞬态(初始朝向未对准切线),盘入主体段单调不增(容差 4px)
    for i in range(12, len(rows) - 1):
        assert rows[i + 1][0] <= rows[i][0] + 4.0, (i, rows[i][0], rows[i + 1][0])
    assert abs(rows[-1][0] - plan.r_min) < 8.0
    # θ 无跳变:每帧角增量 ≤ 转向器上限(MAX_TURN_COIL)留瞬态余量
    from snake_pet.constants import MAX_TURN_COIL
    for i in range(1, len(rows)):
        d = abs(_wrap_pi(rows[i][1] - rows[i - 1][1]))
        assert d <= MAX_TURN_COIL + 0.05, (i, d)


def test_coil_in_bounds_t06():
    # 小 bounds(400×300)内盘旋:身体采样点全程在 bounds 内
    small_bounds = (50, 50, 450, 350)
    s = _make(321, body_segs=40, bounds=small_bounds, pos=(250, 200))
    plan = s.make_coil_plan()
    assert plan is not None
    s.coil = plan
    for _ in range(plan.t_in + plan.dwell + plan.t_out + 20):
        s.move(ACTIVE_STEP, False, [], True)
        for (px, py, _d) in s.path:
            assert small_bounds[0] - 1 <= px <= small_bounds[2] + 1
            assert small_bounds[1] - 1 <= py <= small_bounds[3] + 1
        if s.coil is None:
            break


def test_coil_cancel_when_no_space():
    # 空间不足 → 取消盘旋并回归闲逛(不崩溃、不残留)
    tiny_bounds = (100, 100, 220, 200)
    s = _make(77, body_segs=60, bounds=tiny_bounds, pos=(160, 150))
    plan = s.make_coil_plan()
    assert plan is None
    for _ in range(120):
        s.move(QUIET_STEP, False, [], True)
        (hx, hy) = s.head()
        assert tiny_bounds[0] <= hx <= tiny_bounds[2]
        assert tiny_bounds[1] <= hy <= tiny_bounds[3]


def _headless_app(seed=9):
    random.seed(seed)
    cfg = load_config()
    cfg['autostart'] = False
    return SnakePet(cfg, headless=True)


def _start_coil_eventually(app, tries=10):
    '''游走重试直至盘旋计划可行(蛇在开阔处自然可盘)'''
    for _ in range(tries):
        for _ in range(40):
            app.snake.move(QUIET_STEP, False, [], True)
        app._start_coil()
        if app.snake.coil is not None:
            return app.snake.coil
    return None


def test_coil_interrupt_by_food():
    # 盘旋中途注入食物(活跃档) → ≤30 帧内进入盘出并正常结束,无残留
    app = _headless_app()
    app.snake.body_len = SEG * 60          # 保证非降级多层盘旋
    app.snake.ensure_path_len(app.snake.body_len + 40)
    plan = _start_coil_eventually(app)
    assert plan is not None and not plan.small
    for _ in range(20):
        app._step()
    assert app.snake.coil is plan
    app.foods = [{'x': app.snake.head()[0] + 260, 'y': app.snake.head()[1]}]
    entered_out_at = None
    for i in range(30):
        app._step()
        if app.snake.coil is not None and app.snake.coil.in_out_phase:
            entered_out_at = i + 1
            break
    assert entered_out_at is not None, '食物出现后 30 帧内未进入盘出'
    for _ in range(200):
        app._step()
        if app.snake.coil is None:
            break
    assert app.snake.coil is None
    assert app.snake.forced_angle is None
    app.quit()


def test_coil_interrupt_by_deviation():
    # 盘旋中头部被强制拖离期望点 >60px → 快速盘出并恢复干净状态
    app = _headless_app(seed=10)
    app.snake.body_len = SEG * 60
    app.snake.ensure_path_len(app.snake.body_len + 40)
    plan = _start_coil_eventually(app)
    assert plan is not None
    for _ in range(15):
        app._step()
    # 模拟拎起:把头瞬移到远处(路径尾点同步移动)
    (hx, hy) = app.snake.head()
    last = app.snake.path[-1]
    app.snake.path[-1] = (hx + 150, hy + 150, last[2] + 212)
    for _ in range(300):
        app._step()
        if app.snake.coil is None:
            break
    assert app.snake.coil is None
    assert app.snake.forced_angle is None
    app.quit()


def test_coil_short_snake_degrades():
    # 短蛇(≤10 节)降级为小圈,不报错;更短(2 节)直接跳过
    app = _headless_app(seed=11)
    app.snake.body_len = SEG * 8
    for _ in range(60):
        app.snake.move(QUIET_STEP, False, [], True)
    app._start_coil()
    if app.snake.coil is not None:
        assert app.snake.coil.small
        assert app.snake.coil.revs == 1
    app.snake.coil = None
    app.snake.body_len = SEG * 2
    app.snake.ensure_path_len(app.snake.body_len + 40)
    app._start_coil()
    # 2 节体长连小圈都撑不起 → 取消,不得崩溃
    assert app.snake.coil is None or app.snake.coil.small
    app.quit()
