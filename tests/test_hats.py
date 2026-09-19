'''P4 帽子系统测试 —— T09 锚点矩阵 / 兜底三态 / 配置往返 / 夜间语义'''
import logging
import math
import os
import random

import pytest

from snake_pet.app import SnakePet
from snake_pet.config import load_config, save_config
from snake_pet.constants import QUIET_STEP, SEG
from snake_pet.hats import (DEFAULT_REGISTRY, HAT_IDS, HatRenderer, hats_dir,
                            hat_anchor_pos, load_hat_image, load_registry, render_builtin_hat,
                            resolve_hat)


def test_anchor_matrix_t09():
    # T09:θ ∈ {0°,90°,180°,270°,45°} 锚点与手算矩阵一致(容差 0.5px)
    R = 17.0
    anchor = (0.08, -0.8)
    hx, hy = 500.0, 400.0
    for deg in (0, 90, 180, 270, 45):
        th = math.radians(deg)
        (gx, gy) = hat_anchor_pos(hx, hy, th, anchor, R)
        ex = hx + R * (anchor[0] * math.cos(th) - anchor[1] * math.sin(th))
        ey = hy + R * (anchor[0] * math.sin(th) + anchor[1] * math.cos(th))
        assert math.hypot(gx - ex, gy - ey) < 0.5, deg
    # 手算抽查:θ=0 → (hx + 0.08R, hy - 0.8R);θ=90° → (hx + 0.8R, hy + 0.08R)
    (gx, gy) = hat_anchor_pos(hx, hy, 0.0, anchor, R)
    assert abs(gx - (hx + 0.08 * R)) < 0.5 and abs(gy - (hy - 0.8 * R)) < 0.5
    (gx, gy) = hat_anchor_pos(hx, hy, math.pi / 2, anchor, R)
    assert abs(gx - (hx + 0.8 * R)) < 0.5 and abs(gy - (hy + 0.08 * R)) < 0.5


def test_registry_missing_and_corrupt(tmp_path, monkeypatch):
    # hats.json 缺失 → 默认元数据;坏 JSON → 默认元数据(不抛异常)
    from snake_pet import hats as hm
    monkeypatch.setattr(hm, 'hats_dir', lambda: str(tmp_path))
    reg = load_registry()
    assert set(HAT_IDS).issubset(set(reg.keys()))
    (tmp_path / 'hats.json').write_text('{bad json!!', encoding='utf-8')
    reg2 = load_registry()
    assert set(HAT_IDS).issubset(set(reg2.keys()))


def test_missing_png_falls_back(tmp_path, monkeypatch, caplog):
    # 帽子贴图缺失 → builtin 兜底渲染出非空图,并有 WARNING 日志
    from snake_pet import hats as hm
    monkeypatch.setattr(hm, 'hats_dir', lambda: str(tmp_path))
    with caplog.at_level(logging.WARNING):
        im = load_hat_image('crown')
        assert im is None
        builtin = render_builtin_hat('crown', 64)
    assert builtin is not None and builtin.getbbox() is not None
    assert any('兜底' in r.message or '缺失' in r.message for r in caplog.records)


def test_corrupt_png_falls_back(tmp_path, monkeypatch, caplog):
    from snake_pet import hats as hm
    monkeypatch.setattr(hm, 'hats_dir', lambda: str(tmp_path))
    (tmp_path / 'crown.png').write_bytes(b'\x89PNG\r\n\x1a\nGARBAGE-NOT-A-PNG')
    with caplog.at_level(logging.WARNING):
        im = load_hat_image('crown')
    assert im is None  # 坏图拒绝,走兜底
    assert any('加载失败' in r.message for r in caplog.records)


def test_hat_config_roundtrip_and_invalid(tmp_path):
    p = str(tmp_path / 'cfg.json')
    cfg = load_config(p)
    assert cfg['hat'] == 'auto'
    cfg['hat'] = 'crown'
    save_config(cfg, p)
    assert load_config(p)['hat'] == 'crown'
    # 非法值回落 auto
    cfg['hat'] = 'yellowhat'
    save_config(cfg, p)
    assert load_config(p)['hat'] == 'auto'


def test_resolve_hat_semantics():
    # auto:夜间夜帽/白天无帽;none:无;显式帽:全天;非法:回落 auto
    assert resolve_hat('auto', True) == 'nightcap'
    assert resolve_hat('auto', False) is None
    assert resolve_hat('none', True) is None
    assert resolve_hat('crown', False) == 'crown'
    assert resolve_hat('bogus', True) == 'nightcap'
    assert resolve_hat('bogus', False) is None


def test_renderer_rotates_and_falls_back(monkeypatch, tmp_path):
    # 同一帽子不同朝向渲染出不同旋转;贴图缺失时兜底图非空
    from snake_pet import hats as hm
    monkeypatch.setattr(hm, 'hats_dir', lambda: str(tmp_path))
    hr = HatRenderer()
    a = hr.get('crown', 17.0, 0.0)
    b = hr.get('crown', 17.0, math.pi / 2)
    assert a is not None and b is not None
    assert a[0].size != b[0].size or a[0].tobytes() != b[0].tobytes()
    anchor_same = (a[1], a[2]) == (b[1], b[2])
    assert anchor_same
