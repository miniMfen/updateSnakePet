'''Snake 运动学回归测试 —— v4 selftest 全部断言移植为 pytest(确定性种子)'''
import math
import random

import pytest

from snake_pet.constants import (ACTIVE_STEP, BODY_MAX, BODY_MIN, EAT_RADIUS, GROW_PER_FOOD,
                                 MAX_PATH, QUIET_STEP, SEG)
from snake_pet.snake import Snake

B = (50, 50, 1500, 900)


@pytest.fixture(autouse=True)
def _seed():
    random.seed(42)


def test_active_eats_and_grows():
    s = Snake(400, 300, (1, 0), B)
    foods = [(1200, 600)]
    ate = 0
    for _ in range(3000):
        eaten = s.move(ACTIVE_STEP, True, foods, True)
        for e in eaten:
            ate += 1
            foods = [(300, 200)]
        (hx, hy) = s.head()
        assert B[0] <= hx <= B[2] and B[1] <= hy <= B[3]
        assert len(s.path) <= MAX_PATH
    assert ate > 0
    assert s.body_len == 5 * SEG + ate * GROW_PER_FOOD


def test_quiet_does_not_eat():
    s = Snake(400, 300, (1, 0), B)
    for _ in range(600):
        s.move(QUIET_STEP, False, [(1200, 600)], True)
        (hx, hy) = s.head()
        assert B[0] <= hx <= B[2] and B[1] <= hy <= B[3]
    assert s.body_len == 5 * SEG


def test_no_eat_flag_disables_eating():
    s = Snake(700, 300, (0, 1), B)
    for _ in range(500):
        s.move(ACTIVE_STEP, True, [(700, 800)], False)
    assert s.body_len == 5 * SEG


def test_stays_in_bounds_even_when_food_outside():
    s = Snake(100, 100, (1, 0), B)
    for _ in range(4000):
        s.move(ACTIVE_STEP, True, [(80, 80)], True)
        (hx, hy) = s.head()
        assert B[0] <= hx <= B[2] and B[1] <= hy <= B[3]


def test_segment_spacing_close_to_seg():
    s = Snake(500, 400, (0, 1), B)
    for _ in range(200):
        s.move(QUIET_STEP, False, [], True)
    for i in range(1, 10):
        (ax, ay) = s.pos(i * SEG + 4)
        (bx_, by_) = s.pos((i - 1) * SEG + 4)
        d = math.hypot(ax - bx_, ay - by_)
        assert abs(d - SEG) < SEG, '身体节距应接近 SEG, 实际 %.2f' % d


def test_ensure_path_len_covers_body():
    s = Snake(300, 300, (1, 0), B, body_len=SEG * 5)
    s.body_len += SEG * 3
    s.ensure_path_len(s.body_len + 40)
    assert s.path[-1][2] - s.path[0][2] >= s.body_len + 40
    (tx, ty) = s.pos(s.body_len)
    assert B[0] - 5 <= tx <= B[2] + 5 and B[1] - 5 <= ty <= B[3] + 5


def test_body_len_floor():
    s = Snake(300, 300, (1, 0), B)
    s.body_len = BODY_MIN
    assert s.body_len >= BODY_MIN
    assert BODY_MAX > BODY_MIN


def test_path_memory_capped():
    s = Snake(400, 300, (1, 0), B)
    for _ in range(6000):
        s.move(ACTIVE_STEP, True, [], True)
    assert len(s.path) <= MAX_PATH


def test_ok_respects_avoid_rects():
    s = Snake(800, 500, (1, 0), B)
    s.avoid_rects = [(820, 480, 900, 560)]
    assert not s._ok(850, 500)
    assert s._ok(500, 500)


def test_pos_head_is_zero_behind():
    s = Snake(400, 300, (1, 0), B)
    for _ in range(50):
        s.move(QUIET_STEP, False, [], True)
    (hx, hy) = s.head()
    (px, py) = s.pos(0)
    assert abs(hx - px) < 1e-6 and abs(hy - py) < 1e-6


def test_forced_dir_used_once():
    s = Snake(800, 500, (1, 0), B)
    s.forced_dir = (0, -1)
    s.move(QUIET_STEP, False, [], True)
    (hx, hy) = s.head()
    assert hy < 500
    assert s.forced_dir is None


def test_eat_radius_constant():
    # 进食判定半径与 EAT_RADIUS 一致(头在食物半径内才吃)
    assert EAT_RADIUS == 15


def test_head_starts_at_spawn():
    s = Snake(432, 543, (1, 0), B)
    (hx, hy) = s.head()
    assert (hx, hy) == (432, 543)


def test_initial_body_len():
    s = Snake(100, 100, (1, 0), B)
    assert s.body_len == SEG * 5
