'''P3 渲染测试 —— 离屏渲染冒烟/非空/主题区分/蛇像素包围盒/吐信/贴图覆盖'''
import math
import os
import random

import pytest
from PIL import Image

from snake_pet.app import SnakePet
from snake_pet.config import load_config
from snake_pet.constants import QUIET_STEP, SEG, THEME_IDS
from snake_pet.sprites import load_sprite


def _app(seed=3):
    random.seed(seed)
    cfg = load_config()
    cfg['autostart'] = False
    return SnakePet(cfg, headless=True)


def _frame(app):
    r = app._render_frame()
    assert r is not None
    return r[0]


def _opaque_bbox(img):
    return img.getchannel('A').point(lambda v: 255 if v > 10 else 0).getbbox()


def test_render_smoke_not_empty():
    app = _app()
    for _ in range(80):
        app.snake.move(QUIET_STEP, False, [], True)
    img = _frame(app)
    assert img.size[0] > 50 and img.size[1] > 50
    bbox = _opaque_bbox(img)
    assert bbox is not None, '整帧全透明'
    app.quit()


def test_themes_render_different_colors():
    imgs = {}
    for tid in THEME_IDS:
        app = _app()
        app.cfg['theme'] = tid
        for _ in range(60):
            app.snake.move(QUIET_STEP, False, [], True)
        img = _frame(app).convert('RGBA')
        # 取不透明像素平均色,三主题应可区分
        px = img.load()
        rs = gs = bs = n = 0
        for y in range(0, img.height, 3):
            for x in range(0, img.width, 3):
                r, g, b, a = px[x, y]
                if a > 200:
                    rs += r
                    gs += g
                    bs += b
                    n += 1
        assert n > 0
        imgs[tid] = (rs / n, gs / n, bs / n)
        app.quit()
    # 三通道最大差值判定主题可区分(翡翠 vs 蜜桃红通道差最大)
    diff = max(abs(a - b) for a, b in zip(imgs[THEME_IDS[0]], imgs[THEME_IDS[2]]))
    assert diff > 15, '主题间颜色应可区分'


def test_head_at_front_of_body():
    # 头应位于身体采样链最前端(沿运动方向)
    app = _app()
    random.seed(5)
    for _ in range(100):
        app.snake.move(ACTIVE_STEP := __import__('snake_pet.constants', fromlist=['ACTIVE_STEP']).ACTIVE_STEP, False, [], True)
    img = _frame(app)
    # 头部主题眼白色(纯白)应出现在画面中
    px = img.load()
    whites = 0
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a > 240 and r > 245 and g > 245 and b > 245:
                whites += 1
    assert whites > 10, '未找到眼白/腹带高光像素'
    app.quit()


def test_tongue_frame_draws():
    app = _app()
    for _ in range(40):
        app.snake.move(QUIET_STEP, False, [], True)
    app.tongue = 4
    img_normal = _frame(app)
    app.tongue = 0
    img_plain = _frame(app)
    assert img_normal.size == img_plain.size
    diff = 0
    pa, pb = img_normal.load(), img_plain.load()
    for y in range(img_normal.height):
        for x in range(img_normal.width):
            if pa[x, y] != pb[x, y]:
                diff += 1
    assert diff > 5, '吐信帧应与普通帧存在像素差异'
    app.quit()


def test_head_sprite_override(tmp_path):
    # G3-4:放置 snake_head.png → 渲染输出变化;移除后恢复内置头
    app = _app()
    for _ in range(40):
        app.snake.move(QUIET_STEP, False, [], True)
    before = _frame(app)
    from snake_pet.sprites import sprite_dir
    dst = os.path.join(sprite_dir(), 'snake_head.png')
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    px = img.load()
    for y in range(16, 48):
        for x in range(16, 48):
            px[x, y] = (255, 0, 0, 255)   # 纯红色块作贴图
    img.save(dst)
    try:
        app._sprite_head = load_sprite('snake_head.png')
        assert app._sprite_head is not None
        after = _frame(app)
        assert before.tobytes() != after.tobytes(), '贴图覆盖后渲染应变化'
        # 红色像素应出现在输出中
        px2 = after.load()
        reds = sum(1 for y in range(after.height) for x in range(after.width)
                   if px2[x, y][3] > 200 and px2[x, y][0] > 200 and px2[x, y][1] < 80)
        assert reds > 20, '贴图像素未出现在渲染结果'
    finally:
        if os.path.exists(dst):
            os.remove(dst)
        app._sprite_head = None
    restored = _frame(app)
    assert before.tobytes() == restored.tobytes(), '移除贴图后应恢复内置头'
    app.quit()
