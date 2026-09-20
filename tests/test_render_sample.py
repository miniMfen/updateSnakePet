'''身体采样器回归测试 —— 相邻绘制点距必须恒等于采样步长。

[v5.2 回归背景 · 拖拽身体断层]
_draw_snake 沿「平滑轨迹」按弧长每 step 采样一个身体点。原 _sample_body 对
越界量用**绝对容差**钳制(t>1 且 t<1.5 → 钳到段端),该容差是按安静档步距
(QUIET_STEP=1.6px)标定的。拎起时 _drag_head_to 每帧只落一个路径点,
段长 = DRAG_MAX_STEP = 30px → d 一进段 t 就 >1 → 被钳到段端点
→ 采样点被"吸附回原始折点",相邻间距退化为段长本身(实测 30~35px)。
超过身直径 2*BODY_R=20px,肉眼即「身体断层」。

本文件把「相邻绘制点距 == step」钉成不变量,与路径段长无关。
'''
import math
import random
from collections import deque

import pytest

from snake_pet.app import SnakePet
from snake_pet.config import load_config
from snake_pet.constants import BODY_R, HEAD_R, QUIET_STEP, SEG
from snake_pet.interact import DRAG_MAX_STEP

# 采样步长(与 _draw_snake 内一致)
STEP_SMALL = 5      # body_len <= 1200
STEP_LARGE = 8      # body_len > 1200
D0 = HEAD_R * 1.1


def _app(seed=3):
    random.seed(seed)
    cfg = load_config()
    cfg['autostart'] = False
    return SnakePet(cfg, headless=True)


def _set_path(app, points):
    '''用 (x, y) 列表重建 snake.path,dist 按几何累计'''
    d = 0.0
    path = deque()
    for i, (x, y) in enumerate(points):
        if i:
            d += math.hypot(x - points[i - 1][0], y - points[i - 1][1])
        path.append((float(x), float(y), d))
    app.snake.path = path
    return path


def _straight(app, seg_len, n=160, x0=200.0, y0=300.0):
    return _set_path(app, [(x0 + i * seg_len, y0) for i in range(n)])


def _circle(app, seg_len, n=160, cx=600.0, cy=400.0, r=180.0):
    pts = []
    total = 2 * math.pi * r
    m = max(8, int(total / seg_len))
    for i in range(m + 20):
        a = 2 * math.pi * i / m
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return _set_path(app, pts)


def _gaps(pts):
    return [math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
            for i in range(1, len(pts))]


def _check(app, body_len, step, label):
    rp = app._build_render_path(app.snake)
    pts = app._sample_body(rp, D0, step, body_len)
    assert len(pts) > 10, '%s: 采样点过少(%d)' % (label, len(pts))
    g = _gaps(pts)
    mx = max(g)
    # 直线段上相邻采样点的几何距应恰好 == step;曲线段上 ≤ step
    assert mx <= step * 1.0001, (
        '%s: 相邻绘制点距最大 %.2f px 超过采样步长 %d —— 会露出身体空隙(视觉断层)'
        % (label, mx, step))
    # 相邻点不得重叠(采样器不应把点吸附到同一折点上)
    assert min(g) > step * 0.5, '%s: 相邻绘制点距最小 %.2f px 过小' % (label, min(g))
    return pts, mx


@pytest.mark.parametrize('seg_len', [QUIET_STEP, 8.0, 20.0, DRAG_MAX_STEP, 50.0])
def test_sample_spacing_straight_any_segment_length(seg_len):
    '''直线轨迹:任意路径段长下,相邻绘制点距都必须等于采样步长'''
    app = _app()
    _straight(app, seg_len)
    _check(app, 1500.0, STEP_LARGE, '直线 seg=%.1f' % seg_len)
    app.quit()


@pytest.mark.parametrize('seg_len', [QUIET_STEP, DRAG_MAX_STEP])
def test_sample_spacing_curved(seg_len):
    '''曲线(螺旋近似)轨迹:相邻绘制点距不得超过采样步长'''
    app = _app()
    _circle(app, seg_len)
    _check(app, 1500.0, STEP_LARGE, '圆形 seg=%.1f' % seg_len)
    app.quit()


def test_sample_count_matches_body_length():
    '''采样点数应约等于 (body_len - d0)/step + 1(说明没有整段被跳过)'''
    app = _app()
    _straight(app, DRAG_MAX_STEP)
    for body_len, step in ((1500.0, STEP_LARGE), (900.0, STEP_SMALL)):
        rp = app._build_render_path(app.snake)
        pts = app._sample_body(rp, D0, step, body_len)
        # 采样区间是 [L-body_len, L-d0],故有效长度 = body_len - d0
        want = int((body_len - D0) / step) + 1
        assert abs(len(pts) - want) <= 2, (
            'body_len=%.0f step=%d 采样点 %d,期望约 %d' % (body_len, step, len(pts), want))
    app.quit()


def test_drag_max_step_segments_do_not_break_body():
    '''复现原始缺陷的最小场景:段长 == DRAG_MAX_STEP 的拖动轨迹不得产生 >2*BODY_R 的间距'''
    app = _app()
    _straight(app, DRAG_MAX_STEP)
    rp = app._build_render_path(app.snake)
    pts = app._sample_body(rp, D0, STEP_LARGE, 1500.0)
    mx = max(_gaps(pts))
    assert mx <= 2 * BODY_R, (
        '段长 %s px 时相邻绘制点距 %.2f px 超过身直径 %d px —— 这就是拖拽断层'
        % (DRAG_MAX_STEP, mx, 2 * BODY_R))
    app.quit()


def test_head_junction_has_no_gap():
    '''头锚点到身体最前端采样点的距离应约等于 d0(身体探入头下,衔接不脱节)'''
    app = _app()
    _straight(app, DRAG_MAX_STEP)
    rp = app._build_render_path(app.snake)
    pts = app._sample_body(rp, D0, STEP_LARGE, 1500.0)
    (hx, hy) = (rp[-1][0], rp[-1][1])
    (bx, by) = pts[-1]
    d = math.hypot(hx - bx, hy - by)
    assert d <= D0 + STEP_LARGE, '头→身体前端距 %.2f px 过大(应约 %.1f)' % (d, D0)
    app.quit()
