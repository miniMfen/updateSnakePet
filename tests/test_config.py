'''配置读写测试 —— 默认值/往返/ver<2 迁移/损坏 JSON 容错'''
import json
import os

from snake_pet.config import load_config, save_config
from snake_pet.constants import DEFAULT_CFG


def test_defaults_when_missing(tmp_path):
    p = str(tmp_path / 'cfg.json')
    cfg = load_config(p)
    assert cfg == DEFAULT_CFG
    assert cfg['no_spawn'] is True and cfg['ver'] == 5


def test_roundtrip(tmp_path):
    p = str(tmp_path / 'cfg.json')
    cfg = dict(DEFAULT_CFG)
    cfg['state'] = 'active'
    cfg['no_eat'] = True
    save_config(cfg, p)
    loaded = load_config(p)
    assert loaded['state'] == 'active' and loaded['no_eat'] is True


def test_migration_from_ver1(tmp_path):
    p = str(tmp_path / 'cfg.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'ver': 1, 'no_spawn': False, 'no_eat': False}, f)
    cfg = load_config(p)
    assert cfg['ver'] == 5                      # P6 迁移链 2→5
    assert cfg['no_spawn'] is True              # v1 迁移强制 no_spawn=True(AC-F6-7)
    assert cfg['hat'] == 'auto' and cfg['theme'] == 'jade'  # 新字段补齐


def test_migration_from_v4_config(tmp_path):
    # v4 旧配置(ver=2)读入:既有字段不丢,新字段补齐
    p = str(tmp_path / 'cfg.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'ver': 2, 'no_spawn': True, 'no_eat': True, 'state': 'quiet',
                   'autostart': False}, f)
    cfg = load_config(p)
    assert cfg['no_spawn'] is True and cfg['no_eat'] is True
    assert cfg['state'] == 'quiet' and cfg['autostart'] is False
    assert cfg['hat'] == 'auto' and cfg['theme'] == 'jade' and cfg['ver'] == 5


def test_corrupt_json_falls_back(tmp_path):
    p = str(tmp_path / 'cfg.json')
    with open(p, 'w', encoding='utf-8') as f:
        f.write('{not valid json!!')
    cfg = load_config(p)
    assert cfg == DEFAULT_CFG


def test_extra_fields_preserved(tmp_path):
    p = str(tmp_path / 'cfg.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'ver': 2, 'future_field': 123}, f)
    cfg = load_config(p)
    assert cfg['future_field'] == 123
