'''P6 养成测试 —— T11 消化/阶段/胖瘦/皮肤解锁/成就 + T12 存档闭环'''
import json
import math
import random
import time

import pytest

from snake_pet.app import SnakePet
from snake_pet.config import load_config, save_config
from snake_pet.constants import SEG, SNAKE_THEMES
from snake_pet.growth import (Achievements, digest_step, fatness_of, load_pet_state,
                              save_pet_state, skin_lock_hint, skin_unlocked, stage_baseline,
                              stage_coeff, stage_of)


def test_digest_t11_1():
    # satiety=30 → 体长按速率下降且不低于基线;satiety=50 → 不消化
    base = stage_baseline(0)
    b0 = base + 60.0
    b1 = digest_step(b0, 30.0, 1.0, base)
    assert b0 - b1 == pytest.approx(2.0)          # 2px/s
    b2 = digest_step(base + 1.0, 30.0, 1.0, base)
    assert b2 == base                              # 不低于基线
    b3 = digest_step(base + 60.0, 50.0, 1.0, base)
    assert b3 == base + 60.0                       # 饱食不消化


def test_stage_t11_2():
    # 阈值 19/20 与 99/100 边界
    assert stage_of(19) == 0 and stage_of(20) == 1
    assert stage_of(99) == 1 and stage_of(100) == 2
    assert stage_coeff(0) == 1.0 and stage_coeff(1) == 1.15 and stage_coeff(2) == 1.3
    assert stage_baseline(0) == 5 * SEG
    assert stage_baseline(1) == 8 * SEG
    assert stage_baseline(2) == 12 * SEG


def test_stage_transition_smooth():
    # 阶段切换:渲染系数 2s 内平滑逼近,无跳变(帧采样连续)
    random.seed(3)
    cfg = load_config(str(random.random()))
    cfg['autostart'] = False
    app = SnakePet(cfg, headless=True)
    app._ach.counters['total_eaten'] = 20          # 幼蛇→成蛇
    samples = []
    for _ in range(90):                            # 3s
        app._growth_step(False)
        samples.append(app._stage_render)
    for i in range(1, len(samples)):
        assert samples[i] - samples[i - 1] < 0.02  # 每帧增量有界
    assert samples[-1] > 1.14                       # 已平滑收敛到 1.15
    app.quit()


def test_fatness_t11_3():
    # 连吃 5 颗 w 上升;窗口外回落;clamp 1.25
    now = 1000.0
    times = []
    for _ in range(5):
        times.append(now)
        now += 1
    w = fatness_of(times, now)
    assert w == pytest.approx(1.25)                # 5×0.05=0.25 达上限
    w2 = fatness_of(times, now + 700)              # 10 分钟窗口外全部过期
    assert w2 == pytest.approx(1.0)


def test_skin_unlock_t11_4():
    # 门槛边界:0/10/30/60/100
    assert skin_unlocked(0, 0)
    assert not skin_unlocked(1, 9) and skin_unlocked(1, 10)
    assert not skin_unlocked(2, 29) and skin_unlocked(2, 30)
    assert not skin_unlocked(3, 59) and skin_unlocked(3, 60)
    assert not skin_unlocked(4, 99) and skin_unlocked(4, 100)
    assert skin_lock_hint(1) == '累计吃 10 颗解锁'
    assert skin_lock_hint(0) == ''


def test_achievements_t11_5():
    # 每条只触发一次;counters 累计正确
    ach = Achievements()
    ach.counters['total_feed'] = 1
    assert ach.check() == ['first_feed']
    assert ach.check() == []                       # 二次判定不重复
    ach.counters['total_eaten'] = 10
    news = ach.check()
    assert 'first_eat' in news and 'eater10' in news
    ach.counters['total_eaten'] = 200
    ach.counters['coil_count'] = 10
    ach.counters['pet_count'] = 50
    for d in range(7):
        ach.days.add('2026-09-%02d' % (d + 1))
    news = ach.check()
    assert 'eater50' in news and 'eater100' in news and 'coil10' in news
    assert 'pet50' in news and 'seven_days' in news
    assert ach.count() == (8, 8)
    assert len(ach.names()) == 8


def test_state_roundtrip_and_corrupt(tmp_path):
    # T12:写入→读取往返;坏 JSON → .bak 备份并新建
    p = str(tmp_path / 'pet_state.json')
    st = {'pos': [123.0, 456.0], 'heading': 1.5, 'body_len': 640.0, 'satiety': 33.0,
          'total_eaten': 42, 'affinity': 7, 'skin': 'peach', 'hat': 'crown',
          'achievements': ['first_eat'], 'counters': {'coil_count': 3, 'pet_count': 4,
                                                      'total_eaten': 42, 'total_feed': 9,
                                                      'days': ['2026-09-19']}}
    assert save_pet_state(st, p)
    loaded = load_pet_state(p)
    assert loaded['pos'] == [123.0, 456.0]
    assert loaded['body_len'] == 640.0 and loaded['total_eaten'] == 42
    assert loaded['skin'] == 'peach' and loaded['hat'] == 'crown'
    assert loaded['counters']['coil_count'] == 3
    assert loaded['achievements'] == ['first_eat']
    # 坏档容错
    with open(p, 'w', encoding='utf-8') as f:
        f.write('{broken!!')
    fresh = load_pet_state(p)
    assert fresh['ver'] == 5 and fresh['pos'] is None
    assert any(f.startswith('pet_state.json.bak-') for f in os.listdir(str(tmp_path)))


import os  # noqa: E402  (供上方 tmp_path 断言使用)


def test_periodic_save_clock(tmp_path, monkeypatch):
    # 60s 周期保存:注入时钟验证触发
    from snake_pet import growth as g
    calls = []
    cfg = load_config(str(tmp_path / 'cfg.json'))
    cfg['autostart'] = False
    app = SnakePet(cfg, headless=True)
    monkeypatch.setattr(app, 'save_pet_state_now', lambda reason='x': calls.append(reason))
    app._last_save = time.monotonic() - 61
    app._growth_step(False)
    assert calls == ['periodic']
    app.quit()
