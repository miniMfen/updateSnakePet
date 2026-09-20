'''菜单布局回归测试 —— 面板高度必须装得下全部行。

[v5.2 回归背景]
OPT05 给开关组加了「不再自然变短」,但 MENU_PH 的高度公式里仍硬编码着「开关×4」,
面板因此少算一行(38px):最后一行「退出」被画出画布,在真机上表现为"退出键消失"。
根因是**高度公式与布局各写一份行数**。本文件把「布局必须装得下」钉成不变量,
并强制开关组只有 TOGGLE_ITEMS 一个真源。
'''
import random

from snake_pet.app import SnakePet
from snake_pet.config import load_config


def _app(seed=7):
    random.seed(seed)
    cfg = load_config()
    cfg['autostart'] = False
    return SnakePet(cfg, headless=True)


def _layout(app):
    '''按 _track_menu 的顺序重建布局(不建窗、不推送)'''
    app._menu_rows = []
    app._menu_hits = []
    app._menu_h = 0
    app._menu_layout()


def test_menu_height_matches_prediction():
    '''预估高度(MENU_PH)必须等于布局实测高度 —— 防止高度公式与布局脱钩'''
    app = _app()
    _layout(app)
    assert app._menu_h == app.MENU_PH, (
        '菜单高度预估 %d 与实际 %d 不一致:MENU_FIXED_ROWS / TOGGLE_ITEMS 与布局脱钩,'
        '会裁掉最后一行' % (app.MENU_PH, app._menu_h))
    app.quit()


def test_last_row_is_exit_and_fits_inside_panel():
    '''最后一行必须是「退出」,且完整落在面板内(含底部留白)'''
    app = _app()
    _layout(app)
    assert app._menu_rows, '菜单行不得为空'
    last = app._menu_rows[-1]
    assert last['label'] == '退出', '最后一行应为退出键,实际 %r' % last['label']
    assert last['y'] + last['h'] + app.MENU_PAD == app._menu_h
    assert last['y'] + last['h'] <= app.MENU_PH
    app.quit()


def test_all_hits_inside_panel():
    '''所有命中矩形都必须落在面板内(否则点不到 / 点到面板外误关菜单)'''
    app = _app()
    _layout(app)
    (pw, ph) = (app.MENU_PW, app._menu_ph)
    for (x0, y0, x1, y1, _cb) in app._menu_hits:
        assert 0 <= x0 < x1 <= pw, '命中矩形横向越界 %r' % ((x0, x1),)
        assert 0 <= y0 < y1 <= ph, '命中矩形纵向越界 %r (面板高 %d)' % ((y0, y1), ph)
    app.quit()


def test_toggle_rows_follow_single_source():
    '''布局里的开关行必须与 TOGGLE_ITEMS 一一对应(数量与顺序)'''
    app = _app()
    _layout(app)
    toggles = [r for r in app._menu_rows if r['kind'] == 'toggle']
    assert len(toggles) == len(app.TOGGLE_ITEMS), (
        '开关行 %d 个 vs TOGGLE_ITEMS %d 个' % (len(toggles), len(app.TOGGLE_ITEMS)))
    assert [t['label'] for t in toggles] == [lb for _k, lb in app.TOGGLE_ITEMS]
    app.quit()


def test_exit_row_hit_calls_quit():
    '''退出行的命中回调必须真的调 quit'''
    app = _app()
    _layout(app)
    last = app._menu_rows[-1]
    (y0, y1) = (last['y'], last['y'] + last['h'])
    cbs = [h[4] for h in app._menu_hits if h[1] == y0 and h[3] == y1]
    assert len(cbs) == 1, '退出行应恰好一个全宽命中区,实际 %d 个' % len(cbs)
    called = []
    app.quit = lambda *a, **k: called.append(1)
    cbs[0]()
    assert called == [1], '退出行回调未触发 quit'


def test_menu_height_with_len_editor():
    '''长度输入编辑器展开时,面板必须同样装得下最后一行'''
    app = _app()
    app._len_input = {'text': '12'}
    _layout(app)
    assert app._menu_h == app.MENU_PH
    assert app._menu_rows[-1]['label'] == '退出'
    assert app._menu_rows[-1]['y'] + app._menu_rows[-1]['h'] <= app._menu_ph
    app._len_input = None
    app.quit()


def test_rendered_image_contains_last_row_pixels():
    '''像素级复现:渲染出的图像必须真的把最后一行画进去(不是空白/被裁)'''
    app = _app()
    _layout(app)
    img = app._render_menu_image()
    assert img.height == app._menu_ph, (
        '渲染图像高 %d != 面板高 %d' % (img.height, app._menu_ph))
    last = app._menu_rows[-1]
    y = last['y'] + last['h'] // 2
    assert y < img.height, '最后一行(%s)中心落在画布之外 —— 被裁切' % last['label']
    px = img.load()
    alphas = [px[x, y][3] for x in range(4, app.MENU_PW - 4)]
    assert max(alphas) > 200, '最后一行区域没有面板像素(整行透明=画在面板外)'
    app.quit()
