'''v5.2 BUG-B 回归测试：看门狗遮挡判定 + 重建不再抬升窗口 + SetWindowPos 标志位。

用户反馈(2026-09-21)：小蛇有时会出现在微信等非桌面窗口之上（"应该只在桌面才对"）。

实测到的两个根因：
① `_self_check()` 用 `window_from_point(蛇头) != 自己的 hwnd` 判"是否被遮挡"。
   本机(Win11)实测：该函数在桌面区域**恒定返回桌面图标层 `SysListView32`**
   （连一个"正确的、全不透明的 120×120 分层窗口"也照样命中不到），
   于是"被遮挡"永远为真 → 每 60 秒重建一次窗口
   （snake_pet.log 历史：`长时间被遮挡,主动重建窗口` 663 次 / `遮挡结束` 0 次）。
② `_rebuild_window()` 重建后调 `untopmost_window()`（HWND_NOTOPMOST），
   而该标志的语义是"置于所有非置顶窗口之上" → 把刚创建的窗口钉在普通窗口带最上层，
   于是每次重建都会把蛇抬到微信/资源管理器之上 = 用户看到的现象。
   附带：`SWP_FLAGS = 0x16` 含 `SWP_NOZORDER`，让 sink/untopmost 一直是**空操作**
   （实测调用前后窗口 z 索引恒为 33）。

修复：桌面系窗口不算遮挡；被遮挡期间/遮挡结束**只重推画面不重建窗口**；
      像素陈旧需连续两帧确认；句柄丢失限速重试（避免看门狗永久失效）；
      `SWP_FLAGS` 修正为 NOMOVE|NOSIZE|NOACTIVATE（不含 NOZORDER）。
'''
import snake_pet.app as app_mod
import snake_pet.platform_win as pw
import pytest

from snake_pet.app import SnakePet
from snake_pet.config import load_config
from snake_pet.platform_win import (SWP_FLAGS, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE)

SWP_NOZORDER = 0x0004


class _StubUser32:
    '''替换 platform_win.user32，用于纯逻辑地验证 z 序决策（不真的动窗口）'''

    def __init__(self, foreground):
        self.foreground = foreground
        self.calls = []

    def GetForegroundWindow(self):
        return self.foreground

    def SetWindowPos(self, *args):
        self.calls.append(args)
        return 1


def test_place_below_foreground_skips_desktop_and_self(monkeypatch):
    '''前台是桌面系/自己时不动 z 序（否则可能把自己压到壁纸之下或无事生非）'''
    stub = _StubUser32(0xAAAA)
    monkeypatch.setattr(pw, 'user32', stub)
    monkeypatch.setattr(pw, 'is_desktop_window', lambda h: True)
    assert pw.place_below_foreground_window(0x1234) is False
    assert not stub.calls


def test_place_below_foreground_inserts_after_foreground(monkeypatch):
    '''前台是应用窗口时，把自己插到该窗口正下方（不激活/不移动/不改尺寸）'''
    stub = _StubUser32(0xAAAA)
    monkeypatch.setattr(pw, 'user32', stub)
    monkeypatch.setattr(pw, 'is_desktop_window', lambda h: False)
    assert pw.place_below_foreground_window(0x1234) is True
    assert stub.calls, '应当调用 SetWindowPos'
    args = stub.calls[0]
    assert args[0] == 0x1234 and args[1] == 0xAAAA, '插入锚点必须是前台窗口'
    assert args[6] == SWP_FLAGS, '必须带上不含 NOZORDER 的通用标志'


def test_swp_flags_must_not_contain_nozorder():
    '''SWP_FLAGS 必须含有意声明的三个标志，且绝不含 SWP_NOZORDER。

    带 NOZORDER 时 SetWindowPos 会**忽略 z 序参数**，sink/untopmost 全部失效 ——
    这正是原值 0x16（注释写的是 NOMOVE|NOSIZE|NOACTIVATE，实际却少了 NOSIZE、多了 NOZORDER）
    导致的静默失效。'''
    assert SWP_FLAGS & SWP_NOMOVE
    assert SWP_FLAGS & SWP_NOSIZE
    assert SWP_FLAGS & SWP_NOACTIVATE
    assert not (SWP_FLAGS & SWP_NOZORDER), 'SWP_NOZORDER 会让 z 序修改静默失效'


def _app(monkeypatch, top, top_is_desktop=False):
    '''造一个"有窗口、可断言调用"的 app：只替换外部依赖，其余用真实逻辑'''
    cfg = load_config()
    cfg.update(autostart=False, autosave=False, state='quiet')
    app = SnakePet(cfg, headless=True)
    app.headless = False              # 只为走 _self_check 的非 headless 分支
    app._hwnd = 0x1234
    app.vw, app.vh = 1920, 1080
    monkeypatch.setattr(app_mod, 'window_from_point', lambda x, y: top)
    monkeypatch.setattr(app_mod, 'is_desktop_window', lambda h: top_is_desktop)
    monkeypatch.setattr(app, '_count_head_color_region', lambda *a, **k: 0)
    monkeypatch.setattr(app, '_count_greens_region', lambda *a, **k: 0)
    calls = {'render': 0, 'rebuild': 0}
    monkeypatch.setattr(app, '_render',
                        lambda: calls.__setitem__('render', calls['render'] + 1))
    monkeypatch.setattr(app, '_rebuild_window',
                        lambda: calls.__setitem__('rebuild', calls['rebuild'] + 1))
    return app, calls


def test_desktop_window_is_not_covered(monkeypatch):
    '''命中桌面系窗口 = 正常坐在桌面上，不算被遮挡（否则本机每 60 秒重建一次）'''
    app, calls = _app(monkeypatch, top=0x9999, top_is_desktop=True)
    app._self_check()
    assert app._covered_since is None, '桌面系窗口不应触发遮挡计时'
    assert calls['rebuild'] == 0 and calls['render'] == 0


def test_long_cover_refreshes_instead_of_rebuilding(monkeypatch):
    '''真被应用窗口长期遮挡 → 只重推画面；**不得重建窗口**（重建会抬升 z 序）'''
    app, calls = _app(monkeypatch, top=0x9999, top_is_desktop=False)
    app._self_check()                      # 第一帧：开始计时
    assert app._covered_since is not None
    app._covered_since -= 20.0             # 假装已遮挡 20 秒
    app._last_cover_rebuild = 0.0
    app._self_check()
    assert calls['render'] == 1, '被遮挡期间应当刷新画面'
    assert calls['rebuild'] == 0, '被遮挡期间不得重建窗口'


def test_cover_end_refreshes_instead_of_rebuilding(monkeypatch):
    '''遮挡结束 → 也只刷新画面'''
    app, calls = _app(monkeypatch, top=0x1234)     # top == 自己的 hwnd → 未被遮挡
    app._covered_since = 1.0                       # 装作之前被遮挡过很久
    app._self_check()
    assert calls['render'] == 1
    assert calls['rebuild'] == 0


def test_stale_surface_refreshes_and_never_rebuilds(monkeypatch):
    '''蛇头像素不新鲜 → 只重推画面；**任何情况下都不重建窗口**。

    本机 WindowFromPoint 不可用，无法区分"被别的窗口盖住"(正常)与"合成器冻结"；
    而两者的补救都是重推画面。若在这里重建窗口，就会把蛇抬到前台窗口之上
    （实测：修复中途曾出现"每 3 秒重建一次"的循环）。'''
    app, calls = _app(monkeypatch, top=0x1234)
    for _ in range(2):
        app._self_check()
    assert calls['rebuild'] == 0 and calls['render'] == 0, '连续 2 帧不新鲜不应动作'
    app._self_check()                       # 第 3 帧：重推画面
    assert calls['render'] == 1, '连续 3 帧不新鲜应重推画面'
    assert calls['rebuild'] == 0, '像素不新鲜时绝不允许重建窗口'
    for _ in range(6):                      # 之后立刻再判也不应重复动作(30s 节流)
        app._self_check()
    assert calls['render'] == 1
    assert calls['rebuild'] == 0


def test_fresh_surface_never_rebuilds(monkeypatch):
    '''画面新鲜时不做任何动作（回归：原实现因判定错误一直在重建窗口）'''
    app, calls = _app(monkeypatch, top=0x1234)
    monkeypatch.setattr(app, '_count_head_color_region', lambda *a, **k: 9)
    for _ in range(5):
        app._self_check()
    assert calls['rebuild'] == 0 and calls['render'] == 0


def test_watchdog_never_calls_rebuild_window(monkeypatch):
    '''看门狗整体不应再调用 _rebuild_window（z 序抬升的唯一来源）'''
    app, calls = _app(monkeypatch, top=0x9999, top_is_desktop=False)
    # 覆盖 → 长期覆盖 → 遮挡结束 → 像素不新鲜，全流程走一遍
    app._self_check()
    app._covered_since -= 20.0
    app._self_check()
    app._covered_since = None
    app._hwnd = 0x1234
    monkeypatch.setattr(app_mod, 'window_from_point', lambda x, y: 0x1234)
    for _ in range(6):
        app._self_check()
    assert calls['rebuild'] == 0, '看门狗不应再重建窗口'


def test_lost_hwnd_is_retried_with_throttle(monkeypatch):
    '''句柄丢失后要限速重试创建，否则看门狗永久失效 → 蛇再也不出现'''
    app, calls = _app(monkeypatch, top=0x1234)
    app._hwnd = 0
    created = {'n': 0}

    def fake_create():
        created['n'] += 1
        app._hwnd = 0x5555

    monkeypatch.setattr(app, '_create_window', fake_create)
    app._self_check()
    assert created['n'] == 1, '句柄为空时应尝试重建窗口'
    app._self_check()
    assert created['n'] == 1, '5 秒节流内不应重复创建'


def test_rebuild_resets_cover_state(monkeypatch):
    '''重建后必须清掉遮挡计时与陈旧计数，避免连锁重建'''
    app, calls = _app(monkeypatch, top=0x1234)
    app._covered_since = 123.0
    app._stale_checks = 1
    app._rebuild_window_orig = app._rebuild_window
    # 用真实实现（不替换成计数桩），验证状态被重置
    monkeypatch.setattr(app_mod, 'destroy_window', lambda hwnd: None)
    monkeypatch.setattr(app, '_create_window', lambda: setattr(app, '_hwnd', 0x7777))
    SnakePet._rebuild_window(app)
    assert app._covered_since is None
    assert app._stale_checks == 0
    assert app._hwnd == 0x7777
