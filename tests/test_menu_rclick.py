'''v5.2.2 BUG-C 回归：**非桌面界面**上的鼠标点击不得触发宠物交互。

用户反馈(2026-09-21)：
  「我在其它窗口(比如全屏的 WorkBuddy 开发窗口)时,界面里并没有蛇;但只要我右键的位置
    **刚好与蛇在桌面上的位置重合**,蛇的菜单就会弹出来妨碍我工作。」
  期望：非桌面界面上右键,即使坐标命中蛇身所在位置,也不弹菜单。

根因：`_drain_events()` 的右键分支只做坐标命中判定（`_hit_snake`,半径 40px），
      **没有校验那个屏幕位置上最顶层是哪个窗口**；同文件的左键分支有 `_is_desktop_at`
      做归属校验，右键没有 —— 一处明显的不对称。
      附带 `_is_desktop_at()` 里还有一条 `_hit_snake(x, y) → True` 的自命中短路，
      等于把归属校验自身绕过（且坐标口径错误：传屏幕坐标，而 seg_pos 是世界坐标）。

真机实证(2026-09-21, Win11 2560x1600，证据 reports/BUG_RCLICK_check.json)：
  * 把蛇窗口 `SetWindowPos(HWND_TOPMOST)` 置顶后，`window_from_point(蛇头)` **依然返回**
    桌面图标层 `SysListView32`，从不返回蛇自己的 hwnd
    ⇒ 判据只能写成"最顶层是不是**桌面系**"，不能写成"是不是自己"。
  * 全屏应用窗口盖住桌面时同一点返回该应用窗口（实测 `Chrome_RenderWidgetHostHWND`）。

本文件为**纯新增**：不修改 tests/ 下任何既有断言语义(INV-07)。
全部用例在 headless 实例 + monkeypatch 屏幕归属下运行，不创建真实窗口。
'''
import pytest

import snake_pet.app as app_mod
from snake_pet.app import SnakePet
from snake_pet.config import load_config
from snake_pet.interact import InteractSM

APP_HWND = 0x1234
OTHER_HWND = 0x5678


def _pet():
    cfg = load_config()
    cfg.update(autostart=False, autosave=False, state='auto', no_eat=False,
               no_spawn=False, hat='none')
    return SnakePet(cfg, headless=True)


def _stub_screen(monkeypatch, hwnd, desktop=False, cls='Chrome_RenderWidgetHostHWND',
                 boom=False):
    '''把"这个屏幕点上最顶层是谁"固定下来'''
    def _wfp(x, y):
        if boom:
            raise OSError('模拟 WindowFromPoint 失败')
        return hwnd
    monkeypatch.setattr(app_mod, 'window_from_point', _wfp)
    monkeypatch.setattr(app_mod, 'is_desktop_window', lambda h: desktop)
    monkeypatch.setattr(app_mod, 'get_class_name', lambda h: cls)


@pytest.fixture
def pet():
    app = _pet()
    yield app
    app._quitting = True


# ---------------------------------------------------------------- 归属判据
def test_headless_never_consults_the_screen(monkeypatch, pet):
    '''headless 下直接放行,且**根本不去查屏幕**(保证 soak / render-probe 零额外开销)'''
    monkeypatch.setattr(app_mod, 'window_from_point',
                        lambda x, y: pytest.fail('headless 不应调用 window_from_point'))
    assert pet._point_is_desktop(10, 10) is True


def test_other_app_window_is_not_desktop(monkeypatch, pet):
    '''该点最顶层是别的应用窗口 → 不是桌面(蛇在那里看不见)'''
    pet.headless = False
    _stub_screen(monkeypatch, OTHER_HWND, desktop=False)
    assert pet._point_is_desktop(300, 400) is False


def test_desktop_layer_is_desktop(monkeypatch, pet):
    '''该点最顶层是桌面系窗口(SysListView32 等) → 是桌面'''
    pet.headless = False
    _stub_screen(monkeypatch, 0x9999, desktop=True, cls='SysListView32')
    assert pet._point_is_desktop(300, 400) is True


def test_own_window_counts_as_desktop(monkeypatch, pet):
    '''兜底分支:某些环境下分层窗口会参与命中测试,返回自己也算可见'''
    pet.headless = False
    _stub_screen(monkeypatch, pet._hwnd, desktop=False)
    assert pet._point_is_desktop(300, 400) is True


def test_null_hwnd_does_not_block(monkeypatch, pet):
    '''取不到归属 → 不阻断(与既有 _is_desktop_at 同语义)'''
    pet.headless = False
    _stub_screen(monkeypatch, None, desktop=False)
    assert pet._point_is_desktop(300, 400) is True


def test_screen_query_failure_does_not_block(monkeypatch, pet):
    '''WindowFromPoint 抛异常 → 不阻断(不能因为一次系统调用失败就让宠物变砖)'''
    pet.headless = False
    _stub_screen(monkeypatch, None, boom=True)
    assert pet._point_is_desktop(300, 400) is True


def test_shell_overlay_is_treated_as_desktop(monkeypatch, pet):
    '''shell 全屏透明覆盖层(如 ShellHandwritingCanvas)不算遮挡'''
    pet.headless = False
    _stub_screen(monkeypatch, 0x7777, desktop=False, cls='ShellHandwritingCanvas')
    assert pet._point_is_desktop(300, 400) is True


# ---------------------------------------------------------------- 右键入口
def test_menu_requires_coordinate_hit(monkeypatch, pet):
    '''坐标没落在蛇身上 → 即便在桌面上也不弹菜单'''
    pet.headless = False
    pet.seg_pos = [(100.0, 100.0)]
    _stub_screen(monkeypatch, 0x9999, desktop=True)
    assert pet._should_open_menu_at(400, 400) is False


def test_menu_opens_on_desktop_over_snake(monkeypatch, pet):
    '''桌面 + 坐标命中蛇身 → 弹(功能本身,必须保持)'''
    pet.headless = False
    pet.seg_pos = [(100.0, 100.0)]
    _stub_screen(monkeypatch, 0x9999, desktop=True)
    assert pet._should_open_menu_at(100, 100) is True


def test_menu_rejected_when_snake_is_covered(monkeypatch, pet):
    '''**核心回归**：坐标命中蛇身,但那儿盖着别的应用窗口 → 不弹'''
    pet.headless = False
    pet.seg_pos = [(100.0, 100.0)]
    _stub_screen(monkeypatch, OTHER_HWND, desktop=False)
    assert pet._should_open_menu_at(100, 100) is False


# ------------------------------------------------------- 端到端(事件队列)
def test_drain_events_does_not_open_menu_over_other_window(monkeypatch, pet):
    '''端到端复现用户场景:注入右键 → menu_open 必须保持 False'''
    pet.headless = False
    pet.seg_pos = [(100.0, 100.0)]
    _stub_screen(monkeypatch, OTHER_HWND, desktop=False)
    pet.evq.put(('R', 100, 100))
    pet._drain_events()
    assert pet.menu_open is False


def test_drain_events_opens_menu_on_desktop(monkeypatch, pet):
    '''端到端对照:同样的右键,在桌面上必须照常弹菜单'''
    pet.headless = False
    pet.seg_pos = [(100.0, 100.0)]
    _stub_screen(monkeypatch, 0x9999, desktop=True)
    pet.evq.put(('R', 100, 100))
    pet._drain_events()
    assert pet.menu_open is True


# ---------------------------------------------------------------- 左键分支
def test_left_click_on_covered_snake_neither_pets_nor_feeds(monkeypatch, pet):
    '''蛇被盖住时,左键点它的位置:不进入互动,也不生成食物'''
    pet.headless = False
    pet.seg_pos = [(100.0, 100.0)]
    monkeypatch.setattr(pet, '_hit_snake_head', lambda lx, ly: True)
    _stub_screen(monkeypatch, OTHER_HWND, desktop=False)
    pet.evq.put(('L', 100, 100))
    pet._drain_events()
    assert pet._interact.state == InteractSM.IDLE
    assert pet.foods == []


def test_left_click_on_desktop_still_pets(monkeypatch, pet):
    '''桌面上点蛇头:互动照常(证明修复没有砍掉正常功能)'''
    pet.headless = False
    pet.seg_pos = [(100.0, 100.0)]
    monkeypatch.setattr(pet, '_hit_snake_head', lambda lx, ly: True)
    _stub_screen(monkeypatch, 0x9999, desktop=True)
    pet.evq.put(('L', 100, 100))
    pet._drain_events()
    assert pet._interact.state == InteractSM.PRESS_HEAD


def test_left_click_on_desktop_blank_still_spawns_food(monkeypatch, pet):
    '''桌面空白处左键仍然长苹果(既有行为不变)'''
    pet.headless = False
    pet.seg_pos = []
    _stub_screen(monkeypatch, 0x9999, desktop=True)
    pet.evq.put(('L', 500, 500))
    pet._drain_events()
    assert len(pet.foods) == 1


def test_left_click_on_other_window_does_not_spawn_food(monkeypatch, pet):
    '''别的应用窗口上左键不再"隔空"长出苹果'''
    pet.headless = False
    pet.seg_pos = []
    _stub_screen(monkeypatch, OTHER_HWND, desktop=False)
    pet.evq.put(('L', 500, 500))
    pet._drain_events()
    assert pet.foods == []


# --------------------------------------------------- 归属校验不再被短路绕过
def test_is_desktop_at_has_no_self_hit_shortcut(monkeypatch, pet):
    '''[v5.2.2] `_is_desktop_at` 不再因"坐标命中蛇身"就返回 True'''
    pet.headless = False
    pet.seg_pos = [(100.0, 100.0)]
    _stub_screen(monkeypatch, OTHER_HWND, desktop=False)
    assert pet._is_desktop_at(100, 100) is False
    _stub_screen(monkeypatch, 0x9999, desktop=True)
    assert pet._is_desktop_at(100, 100) is True


def test_is_desktop_at_matches_point_is_desktop(monkeypatch, pet):
    '''[v5.2.2] 两个入口必须是同一套判据(headless 早退除外)'''
    pet.headless = False
    _stub_screen(monkeypatch, 0x9999, desktop=True)
    assert pet._is_desktop_at(7, 9) == pet._point_is_desktop(7, 9)
    _stub_screen(monkeypatch, OTHER_HWND, desktop=False)
    assert pet._is_desktop_at(7, 9) == pet._point_is_desktop(7, 9) is False
