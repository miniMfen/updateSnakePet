'''养成系统数值核心(P6) —— 阶段/消化基线/胖瘦/皮肤解锁/成就/存档。
纯逻辑、时钟可注入,全部可单测;Win32 与渲染不掺和。'''
import json
import logging
import math
import os
import time

from .config import base_dir
from .constants import (ACHIEVEMENTS, DIGEST_PX_PER_SEC, DIGEST_SATIETY_BELOW, FATNESS_MAX,
                        FATNESS_PER_EAT, FATNESS_WINDOW_SEC, PET_STATE_FILE, SKIN_UNLOCK_EATEN,
                        STAGE_BASELINE_SEG, STAGE_COEFF, STAGE_TOTAL_EATEN)


# ---- 阶段 ----
def stage_of(total_eaten):
    '''累计进食 → 阶段序号 0 幼蛇 / 1 成蛇 / 2 大蛇'''
    if total_eaten >= STAGE_TOTAL_EATEN[1]:
        return 2
    if total_eaten >= STAGE_TOTAL_EATEN[0]:
        return 1
    return 0


def stage_coeff(stage):
    return STAGE_COEFF[stage]


def stage_baseline(stage):
    '''该阶段的体长下限(px)'''
    return STAGE_BASELINE_SEG[stage] * 20  # SEG=20;不直接 import 防循环


# ---- 消化 ----
def digest_step(body_len, satiety, dt, baseline):
    '''satiety < 40 时体长按 DIGEST_PX_PER_SEC 回落,不低于阶段基线;返回新体长'''
    if satiety >= DIGEST_SATIETY_BELOW:
        return body_len
    return max(float(baseline), body_len - DIGEST_PX_PER_SEC * dt)


# ---- 胖瘦 ----
def fatness_of(eat_times, now):
    '''滚动窗口进食数 → 圆润系数 w = 1.0 + min(n×0.05, 0.25)'''
    n = sum(1 for t in eat_times if now - t <= FATNESS_WINDOW_SEC)
    return 1.0 + min(n * FATNESS_PER_EAT, FATNESS_MAX)


# ---- 皮肤解锁 ----
def skin_unlocked(skin_index, total_eaten):
    return total_eaten >= SKIN_UNLOCK_EATEN[skin_index]


def skin_lock_hint(skin_index):
    need = SKIN_UNLOCK_EATEN[skin_index]
    return '累计吃 %d 颗解锁' % need if need > 0 else ''


# ---- 成就 ----
class Achievements:
    '''成就引擎:解锁仅一次;解锁时返回新成就列表供 UI 播报'''

    def __init__(self, unlocked=None, counters=None, days=None):
        self.unlocked = set(unlocked or [])
        self.counters = counters or {}
        self.days = set(days or [])

    def check(self):
        '''按 counters/days 重新判定,返回本次新解锁的成就 id 列表'''
        total_eaten = self.counters.get('total_eaten', 0)
        cond = {
            'first_feed': self.counters.get('total_feed', 0) >= 1,
            'first_eat': total_eaten >= 1,
            'eater10': total_eaten >= 10,
            'eater50': total_eaten >= 50,
            'eater100': total_eaten >= 100,
            'seven_days': len(self.days) >= 7,
            'coil10': self.counters.get('coil_count', 0) >= 10,
            'pet50': self.counters.get('pet_count', 0) >= 50,
        }
        news = []
        for (aid, _name, _desc) in ACHIEVEMENTS:
            if cond.get(aid) and aid not in self.unlocked:
                self.unlocked.add(aid)
                news.append(aid)
        return news

    def count(self):
        return len(self.unlocked), len(ACHIEVEMENTS)

    def names(self):
        m = {aid: name for (aid, name, _d) in ACHIEVEMENTS}
        return [m[a] for a in self.unlocked if a in m]


# ---- 存档 ----
PET_STATE_VER = 5


def pet_state_path():
    return os.path.join(base_dir(), PET_STATE_FILE)


def default_state():
    return {
        'pos': None,
        'heading': 0.0,
        'body_len': 100.0,
        'satiety': 70.0,
        'total_eaten': 0,
        'affinity': 0,
        'skin': 'jade',
        'hat': 'auto',
        'achievements': [],
        'counters': {'coil_count': 0, 'pet_count': 0, 'total_eaten': 0,
                     'total_feed': 0, 'days': []},
        'ts': time.time(),
        'ver': PET_STATE_VER,
    }


def save_pet_state(state, path=None):
    p = path or pet_state_path()
    state = dict(state)
    state['ts'] = time.time()
    state['ver'] = PET_STATE_VER
    try:
        tmp = p + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
        return True
    except Exception as e:
        logging.warning('存档写入失败: %r', e)
        return False


def load_pet_state(path=None):
    '''读取存档;文件不存在返回 None(全新宠物);
    损坏 → 改名 .bak-<ts> 后返回默认新档;字段缺省按默认补齐'''
    p = path or pet_state_path()
    if not os.path.exists(p):
        return None
    state = default_state()
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError('存档根不是对象')
        state.update({k: v for k, v in data.items() if v is not None})
        state['counters'] = {**default_state()['counters'], **(data.get('counters') or {})}
        state['achievements'] = list(data.get('achievements') or [])
        return state
    except Exception as e:
        if os.path.exists(p):
            bak = '%s.bak-%d' % (p, int(time.time()))
            try:
                os.replace(p, bak)
                logging.warning('存档损坏(%r),已备份到 %s 并新建', e, bak)
            except OSError:
                logging.warning('存档损坏(%r),备份失败,新建', e)
        return state
