'''入口与 CLI 分发:
  python -m snake_pet                  正常启动
  python -m snake_pet --selftest       运动学断言 + 模块自检
  python -m snake_pet --soak N         N 秒无人值守浸泡, 输出 JSON 报告
  python -m snake_pet --soak N --headless   跳过真实窗口, 仅跑逻辑+离屏渲染
  python -m snake_pet --render-probe DIR    确定性渲染 8 张代表帧 PNG
'''
import json
import logging
import math
import os
import random
import sys
import time

from .app import SnakePet, main as app_main, selftest
from .config import base_dir, load_config
from .constants import MAX_FOODS, QUIET_STEP, SATIETY_START, SEG, TICK_MS
from .interact import InteractSM
from .platform_win import working_set_mb


def _isolate_tool_home():
    '''soak/探针强制使用独立存档目录,不污染用户真实宠物状态(v5.1)'''
    if os.environ.get('SNAKEPET_TOOL_HOME'):
        return
    tool_home = os.path.join(base_dir(), 'reports', '_tool_home')
    os.makedirs(tool_home, exist_ok=True)
    os.environ['SNAKEPET_HOME'] = tool_home
    os.environ['SNAKEPET_TOOL_HOME'] = '1'


def run_soak(seconds, headless=False, out=None):
    '''无人值守浸泡:驱动主循环逻辑(可选真实窗口),结束输出统计 JSON。
    异常列表非空 → 退出码 1'''
    _isolate_tool_home()
    log_path = os.path.join(base_dir(), 'snake_pet.log')
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', filename=log_path)
    cfg = load_config()
    cfg['no_spawn'] = False
    cfg['autostart'] = False
    cfg['state'] = 'auto'
    random.seed(20260919)
    app = SnakePet(cfg, headless=headless)
    mem_start = working_set_mb()
    foods_eaten = 0
    orig_on_eat = app._on_eat

    def counted_on_eat():
        nonlocal foods_eaten
        foods_eaten += 1
        logging.info('soak 追食: 第 %d 次吃到食物 (body_len=%.0f)', foods_eaten, app.snake.body_len)
        orig_on_eat()

    app._on_eat = counted_on_eat
    exceptions = []
    path_max = 0
    fx_max = 0
    coils = 0
    in_coil = False
    drags = 0
    in_drag = False
    pets_start = app._interact.affinity
    gesture = None
    frame_ms = []
    frames = 0
    t0 = time.monotonic()
    deadline = t0 + seconds
    next_food = t0 + 2.0
    last = t0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now - last >= TICK_MS / 1000:
            last = now
            ft0 = time.perf_counter()
            try:
                app._drain_events()
                app._step()
            except Exception as e:
                exceptions.append(repr(e))
                if len(exceptions) >= 100:
                    break
            frame_ms.append((time.perf_counter() - ft0) * 1000.0)
            frames += 1
            path_max = max(path_max, len(app.snake.path))
            fx_max = max(fx_max, len(app.fx))
            if app.snake.coil is not None and not in_coil:
                coils += 1
                in_coil = True
                logging.info('soak 盘旋: 第 %d 次盘旋开始', coils)
            elif app.snake.coil is None:
                in_coil = False
            if app._interact.state == InteractSM.DRAG and not in_drag:
                drags += 1
                in_drag = True
            elif app._interact.state != InteractSM.DRAG:
                in_drag = False
            # 随机手势注入(模拟用户:抚摸/拎起/点击)
            if gesture is None:
                if random.random() < 0.008:
                    (hx, hy) = app.snake.head()
                    kind = random.choice(('pet', 'drag', 'click'))
                    gesture = {'kind': kind, 't': 0, 'x': hx + app.vx, 'y': hy + app.vy,
                               'dx': random.uniform(-8, 8), 'dy': random.uniform(-8, 8)}
                    app.evq.put(('L', gesture['x'], gesture['y']))
            else:
                gesture['t'] += 1
                if gesture['kind'] == 'drag' and gesture['t'] % 3 == 0 and gesture['t'] < 33:
                    gesture['x'] += gesture['dx'] * 8
                    gesture['y'] += gesture['dy'] * 8
                    app.evq.put(('MOVE', gesture['x'], gesture['y']))
                hold = 30 if gesture['kind'] == 'pet' else (36 if gesture['kind'] == 'drag' else 2)
                if gesture['t'] >= hold:
                    app.evq.put(('LU', gesture['x'], gesture['y']))
                    gesture = None
        if now >= next_food:
            next_food = now + 25.0
            # 爆发式撒食 1~2 颗(模拟用户点击),留出足够长的无食物窗口让空闲盘旋得以触发
            bx0, by0, bx1, by1 = app.bounds
            for _ in range(random.randint(1, 2)):
                if len(app.foods) < MAX_FOODS:
                    app._spawn_food(random.uniform(bx0, bx1), random.uniform(by0, by1))
            if now - t0 > seconds * 0.5:
                # soak 后半段保持低饱食度,让消化路径可观测(G6-5)
                app.satiety = min(app.satiety, 28.0)
                logging.info('soak 消化观察: satiety 压至 %.1f', app.satiety)
        time.sleep(0.002)
    elapsed = max(1e-6, time.monotonic() - t0)
    mem_end = working_set_mb()
    app.quit()
    report = {
        'seconds': seconds,
        'headless': headless,
        'fps_avg': round(frames / elapsed, 2),
        'fps_min': round(1000.0 / max(frame_ms), 2) if frame_ms else 0.0,
        'frame_ms_avg': round(sum(frame_ms) / len(frame_ms), 3) if frame_ms else 0.0,
        'frame_ms_max': round(max(frame_ms), 3) if frame_ms else 0.0,
        'mem_start_mb': round(mem_start, 1),
        'mem_end_mb': round(mem_end, 1),
        'mem_delta_mb': round(mem_end - mem_start, 1),
        'exceptions': exceptions,
        'foods_eaten': foods_eaten,
        'coils': coils,
        'drags': drags,
        'pets': app._interact.affinity - pets_start,
        'path_max': path_max,
        'fx_max': fx_max,
        'log_path': log_path,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            f.write(text)
    return 1 if exceptions else 0


def run_probe(outdir):
    '''确定性种子渲染代表帧 PNG + probe_index.json(独立存档,不做自动存档)'''
    import logging
    _isolate_tool_home()
    logging.basicConfig(level=logging.WARNING)
    os.makedirs(outdir, exist_ok=True)
    random.seed(20260919)
    cfg = load_config()
    cfg['autostart'] = False
    cfg['autosave'] = False
    app = SnakePet(cfg, headless=True)
    b = app.bounds
    scenes = []

    def snap(name, note):
        r = app._render_frame()
        files = []
        if r is not None:
            (img, wx, wy) = r
            fn = f'probe_{len(scenes) + 1:02d}_{name}.png'
            img.save(os.path.join(outdir, fn))
            files.append({'file': fn, 'size': list(img.size)})
        scenes.append({'scene': name, 'note': note, 'files': files})

    # 1 正常游动:安静档闲逛一段
    random.seed(11)
    for _ in range(120):
        app.snake.move(QUIET_STEP, False, [], True)
    snap('游动', '安静档 360° 闲逛后的身体形态')

    # 2 追食:活跃档朝食物追一段
    random.seed(22)
    (hx, hy) = app.snake.head()
    app.foods = [{'x': min(hx + 320, b[2] - 40), 'y': min(hy + 220, b[3] - 40)}]
    for _ in range(60):
        app._step()
    snap('追食', '活跃档直线追向食物')

    # 3 吃食瞬间:食物贴头 + flash/wag + 粒子
    (hx, hy) = app.snake.head()
    app.foods = [{'x': hx + 6, 'y': hy}]
    app._on_eat()
    snap('吃食瞬间', '进食白闪/摆尾/星星粒子')

    # 4 睡觉+Z:饱食度归零
    app.foods = []
    app.satiety = 0.0
    app._sleep_since = time.monotonic()
    app._sleep_dur = 20
    app._mood_timers()
    app._spawn_zdan()
    r = app._render_frame()
    if r is not None:
        (img, wx, wy) = r
        img.save(os.path.join(outdir, f'probe_{len(scenes) + 1:02d}_睡觉.png'))
        scenes.append({'scene': '睡觉', 'note': '闭眼+zzz+Z弹幕', 'files': [{'file': f'probe_{len(scenes) + 1:02d}_睡觉.png', 'size': list(img.size)}]})

    # 5 分层盘旋:触发真实盘旋并推进到盘踞段(多层同心圈)
    app.satiety = SATIETY_START
    app._sleep_since = None
    app.foods = []
    app.snake.body_len = SEG * 60          # 多层盘旋需要足够体长
    app.snake.ensure_path_len(app.snake.body_len + 40)
    app.wag = 0                            # 清掉场景3的摆尾,避免盘旋触发被守卫拦截
    random.seed(55)
    for _ in range(10):
        for _ in range(50):
            app.snake.move(QUIET_STEP, False, [], True)
        app._start_coil()
        if app.snake.coil is not None:
            break
    assert app.snake.coil is not None, '盘旋计划未生成(空间/体长不可行)'
    for _ in range(app.snake.coil.t_in + 20):
        app._step()
        if app.snake.coil is None:
            break
    snap('盘旋', '分层盘旋:盘入→盘踞的阿基米德螺线多层圈')

    # 6~9 夜帽四朝向(G4-2:旋转 ≤15° 视觉差)
    app.cfg['hat'] = 'nightcap'
    random.seed(66)
    for _ in range(60):
        app.snake.move(QUIET_STEP, False, [], True)
    for deg, name in ((0, '夜帽0度'), (90, '夜帽90度'), (180, '夜帽180度'), (270, '夜帽270度')):
        app.snake.heading_angle = math.radians(deg)
        app.snake._wander_target = app.snake.heading_angle
        app._render_frame()
        snap(name, '夜帽随朝向旋转 %d°' % deg)

    # 10~15 帽子衣柜:其余 6 顶
    for hid, hname in (('santa', '圣诞'), ('crown', '皇冠'), ('graduation', '学士'),
                       ('tophat', '礼帽'), ('cap_blue', '棒球'), ('bowknot', '蝴蝶结')):
        app.cfg['hat'] = hid
        snap('帽子' + hname, '帽子衣柜:%s' % hname)
    app.cfg['hat'] = 'auto'

    # 16/17 主题切换:经典绿、蜜桃粉(默认翡翠玉蛇见其他场景)
    from snake_pet.constants import THEME_IDS
    for tid, name in (('classic', '主题经典绿'), ('peach', '主题蜜桃粉')):
        app.cfg['theme'] = tid
        snap(name, '配色主题切换效果')
    app.cfg['theme'] = THEME_IDS[0]

    # 18 吐信动画帧(取完全伸出帧)
    app.tongue = 4
    snap('吐信', '红色两叉吐信弹出帧')
    app.tongue = 0

    # 19 长蛇 100 节
    app.snake.body_len = SEG * 100
    app.snake.ensure_path_len(app.snake.body_len + 200)
    random.seed(88)
    for _ in range(240):
        app.snake.move(QUIET_STEP, False, [], True)
    snap('长蛇100节', '100 节长蛇的锥形/斑纹/采样与窗口扩缩')

    # 20 菜单打开
    app._menu_layout()
    img = app._render_menu_image()
    idx = len(scenes) + 1
    img.save(os.path.join(outdir, f'probe_{idx:02d}_菜单.png'))
    scenes.append({'scene': '菜单', 'note': '右键菜单面板 254px 宽', 'files': [{'file': f'probe_{idx:02d}_菜单.png', 'size': list(img.size)}]})

    index = {'probe': scenes, 'bounds': list(app.bounds)}
    with open(os.path.join(outdir, 'probe_index.json'), 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    app.quit()
    print(f'render-probe 完成: {len(scenes)} 场景 → {os.path.abspath(outdir)}')
    return 0


def cli(argv):
    if '--selftest' in argv:
        selftest()
        return 0
    if '--soak' in argv:
        i = argv.index('--soak')
        seconds = int(argv[i + 1]) if i + 1 < len(argv) else 60
        headless = '--headless' in argv or '--soak-headless' in argv
        out = None
        if '--out' in argv:
            out = argv[argv.index('--out') + 1]
        return run_soak(seconds, headless=headless, out=out)
    if '--render-probe' in argv:
        outdir = argv[argv.index('--render-probe') + 1]
        return run_probe(outdir)
    app_main()
    return 0


if __name__ == '__main__':
    sys.exit(cli(sys.argv[1:]))
