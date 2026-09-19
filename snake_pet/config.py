'''配置读写与版本迁移(v4 语义保持, 存取路径可注入便于测试)'''
import json
import logging
import os
import sys

from .constants import APP_NAME, DEFAULT_CFG


def base_dir():
    r'''可写目录:打包成 exe 时用 %APPDATA%\SnakePet;源码运行时优先仓库根目录
    (即 snake_pet 包的上一级);可用环境变量 SNAKEPET_HOME 覆盖'''
    env = os.environ.get('SNAKEPET_HOME')
    if env:
        os.makedirs(env, exist_ok=True)
        return env
    if getattr(sys, 'frozen', False):
        d = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), APP_NAME)
        os.makedirs(d, exist_ok=True)
        return d
    d = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        probe = os.path.join(d, '.wtest')
        with open(probe, 'w') as f:
            f.write('')
        os.remove(probe)
        return d
    except OSError:
        d = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), APP_NAME)
        os.makedirs(d, exist_ok=True)
        return d


def config_path():
    return os.path.join(base_dir(), 'snake_pet_config.json')


def load_config(path=None):
    '''读取配置;迁移链 ver<5 → 补 hat/theme 等新字段并置 ver=5
    (v2 语义 no_spawn=True 保持);损坏文件回退默认值;非法帽子值回落 auto'''
    from .hats import DEFAULT_REGISTRY
    cfg = dict(DEFAULT_CFG)
    p = path or config_path()
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            if data.get('ver', 0) < 5:
                data = dict(data)
                if data.get('ver', 0) < 2:
                    data['no_spawn'] = True   # v1→v2 迁移语义保持(AC-F6-7)
                data.setdefault('hat', 'auto')     # P4
                data.setdefault('theme', 'jade')   # P6 皮肤选择
                data['ver'] = 5
        cfg.update(data)
        if cfg.get('hat') not in ('auto', 'none') and cfg.get('hat') not in DEFAULT_REGISTRY:
            cfg['hat'] = 'auto'
        return cfg
    except Exception as e:
        logging.warning('读取配置失败, 使用默认值: %r', e)
        return cfg


def save_config(cfg, path=None):
    p = path or config_path()
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning('保存配置失败: %r', e)
