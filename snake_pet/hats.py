'''帽子衣柜(P4) —— 7 顶帽子,随 360° 朝向旋转;贴图 + 内置手绘双通道。
元数据 sprites/hats/hats.json;缺图/坏图/清单缺失时走 builtin_fallback 并告警。'''
import json
import logging
import math
import os

from PIL import Image, ImageDraw

from .sprites import sprite_dir

HATS_SUBDIR = 'hats'

# 默认元数据(与 sprites/hats/hats.json 同构)
# anchor: 相对头半径的佩戴点(x 沿 heading, y 沿头顶方向, 负=向上)
# pivot: 贴图内的"佩戴线"位置(占图宽/高的比例)——佩戴点对齐该处,默认底边中心(0.5,1.0)
# pivot_y 越小=帽子相对佩戴点越"抬升"。第一排帽(夜帽/圣诞/皇冠)逐顶校准过。
DEFAULT_REGISTRY = {
    'nightcap': {'name': '夜帽', 'anchor': [0.0, -0.72], 'scale': 1.25,
                 'base_offset_deg': 35, 'builtin_fallback': 'nightcap',
                 'pivot': [0.58, 0.92]},
    'santa': {'name': '圣诞', 'anchor': [0.0, -0.72], 'scale': 1.1,
              'base_offset_deg': 30, 'builtin_fallback': 'santa',
              'pivot': [0.5, 0.94]},
    'crown': {'name': '皇冠', 'anchor': [0.0, -0.88], 'scale': 0.82,
              'base_offset_deg': 0, 'builtin_fallback': 'crown'},
    'graduation': {'name': '学士', 'anchor': [0.0, -0.78], 'scale': 1.2,
                   'base_offset_deg': 0, 'builtin_fallback': 'graduation',
                   'pivot': [0.5, 0.62]},
    'tophat': {'name': '礼帽', 'anchor': [0.0, -0.82], 'scale': 1.1,
               'base_offset_deg': 0, 'builtin_fallback': 'tophat',
               'pivot': [0.5, 0.88]},
    'cap_blue': {'name': '棒球', 'anchor': [0.06, -0.72], 'scale': 1.1,
                 'base_offset_deg': 0, 'builtin_fallback': 'cap_blue',
                 'pivot': [0.5, 0.7]},
    'bowknot': {'name': '蝴蝶结', 'anchor': [-0.18, -0.66], 'scale': 0.92,
                'base_offset_deg': 0, 'builtin_fallback': 'bowknot',
                'pivot': [0.5, 0.6]},
}
HAT_IDS = tuple(DEFAULT_REGISTRY.keys())


def hats_dir():
    return os.path.join(sprite_dir(), HATS_SUBDIR)


def load_registry():
    '''读 hats.json;缺失/损坏回退默认元数据(告警,不抛异常)'''
    p = os.path.join(hats_dir(), 'hats.json')
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and data:
            merged = {k: dict(v) for k, v in DEFAULT_REGISTRY.items()}
            merged.update(data)
            return merged
        logging.warning('hats.json 内容无效,使用默认帽子元数据')
    except FileNotFoundError:
        logging.warning('hats.json 缺失,使用默认帽子元数据')
    except Exception as e:
        logging.warning('hats.json 读取失败(%r),使用默认帽子元数据', e)
    return {k: dict(v) for k, v in DEFAULT_REGISTRY.items()}


def load_hat_image(hat_id):
    '''加载帽子贴图;缺失/坏图返回 None(调用方走内置兜底)并告警'''
    p = os.path.join(hats_dir(), hat_id + '.png')
    try:
        if os.path.exists(p):
            return Image.open(p).convert('RGBA')
        logging.warning('帽子贴图缺失: %s.png,使用内置兜底绘制', hat_id)
    except Exception as e:
        logging.warning('帽子贴图 %s 加载失败(%r),使用内置兜底绘制', hat_id, e)
    return None


def resolve_hat(cfg_hat, is_night):
    '''帽子决策:'auto'=夜间 nightcap/白天无帽;'none'=无帽;其余为显式帽 id。
    非法值回落 'auto'(与 v4 夜间自动语义一致)'''
    if cfg_hat == 'none':
        return None
    if cfg_hat in DEFAULT_REGISTRY:
        return cfg_hat
    if cfg_hat != 'auto':
        logging.warning('非法帽子配置 %r,回落 auto', cfg_hat)
    return 'nightcap' if is_night else None


def hat_anchor_pos(hx, hy, theta, anchor, R):
    '''帽子锚点:anchor.x 沿 heading、anchor.y 沿头「头顶」方向(旋转系)。
    T09 的被测纯函数'''
    ax, ay = anchor
    return (hx + R * (ax * math.cos(theta) - ay * math.sin(theta)),
            hy + R * (ax * math.sin(theta) + ay * math.cos(theta)))


def render_builtin_hat(hat_id, width):
    '''内置手绘兜底帽(简化卡通风),返回 RGBA 图'''
    w = max(12, int(width))
    h = max(10, int(width * 0.8))
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = w / 2

    def cone(color, dark, tip_dx=-0.18 * w, tip_y=0.08 * h, tilt=0.0):
        pts = [(cx - 0.46 * w, h * 0.82), (cx + 0.46 * w, h * 0.82),
               (cx + tip_dx, tip_y)]
        d.polygon(pts, fill=color + (255,))
        d.ellipse([cx - 0.5 * w, h * 0.68, cx + 0.5 * w, h * 0.98], fill=dark + (255,))

    if hat_id == 'nightcap':
        cone((139, 130, 226), (111, 102, 205))
        d.ellipse([cx + 0.30 * w, h * 0.02, cx + 0.52 * w, h * 0.24], fill=(255, 255, 255, 255))
    elif hat_id == 'santa':
        cone((235, 60, 60), (250, 246, 240), tip_dx=-0.22 * w, tip_y=0.02 * h)
        d.ellipse([cx - 0.16 * w, h * 0.0, cx + 0.12 * w, h * 0.24], fill=(255, 255, 255, 255))
    elif hat_id == 'crown':
        base = h * 0.78
        d.polygon([(cx - 0.44 * w, base), (cx - 0.44 * w, h * 0.34),
                   (cx - 0.22 * w, h * 0.56), (cx, h * 0.22),
                   (cx + 0.22 * w, h * 0.56), (cx + 0.44 * w, h * 0.34),
                   (cx + 0.44 * w, base)], fill=(247, 187, 63, 255))
        d.rectangle([cx - 0.44 * w, base, cx + 0.44 * w, h * 0.92], fill=(232, 165, 44, 255))
        for k in (-0.26, 0.0, 0.26):
            d.ellipse([cx + k * w - 3, h * 0.80, cx + k * w + 3, h * 0.90],
                      fill=(70, 130, 220, 255))
    elif hat_id == 'graduation':
        d.polygon([(cx, h * 0.10), (cx + 0.5 * w, h * 0.34), (cx, h * 0.58),
                   (cx - 0.5 * w, h * 0.34)], fill=(48, 44, 76, 255))
        d.rectangle([cx - 0.26 * w, h * 0.5, cx + 0.26 * w, h * 0.72], fill=(58, 52, 88, 255))
        d.line([cx, h * 0.30, cx + 0.36 * w, h * 0.52], fill=(240, 196, 74, 255), width=3)
        d.ellipse([cx + 0.32 * w, h * 0.5, cx + 0.42 * w, h * 0.62], fill=(240, 196, 74, 255))
    elif hat_id == 'tophat':
        d.ellipse([cx - 0.5 * w, h * 0.72, cx + 0.5 * w, h * 0.98], fill=(46, 42, 60, 255))
        d.rectangle([cx - 0.32 * w, h * 0.08, cx + 0.32 * w, h * 0.86], fill=(56, 50, 74, 255))
        d.rectangle([cx - 0.32 * w, h * 0.6, cx + 0.32 * w, h * 0.74], fill=(226, 64, 116, 255))
    elif hat_id == 'cap_blue':
        d.polygon([(cx - 0.44 * w, h * 0.72), (cx + 0.36 * w, h * 0.72),
                   (cx + 0.28 * w, h * 0.30), (cx - 0.30 * w, h * 0.30)],
                  fill=(64, 132, 240, 255))
        d.ellipse([cx + 0.28 * w, h * 0.58, cx + 0.78 * w, h * 0.78], fill=(52, 112, 214, 255))
        d.ellipse([cx - 0.06 * w, h * 0.22, cx + 0.06 * w, h * 0.34], fill=(240, 248, 255, 255))
    elif hat_id == 'bowknot':
        for sgn in (-1.0, 1.0):
            d.polygon([(cx, h * 0.5), (cx + sgn * 0.46 * w, h * 0.16),
                       (cx + sgn * 0.46 * w, h * 0.84)], fill=(232, 62, 92, 255))
        d.ellipse([cx - 0.12 * w, h * 0.34, cx + 0.12 * w, h * 0.66], fill=(255, 108, 132, 255))
    else:
        d.ellipse([cx - 0.4 * w, h * 0.2, cx + 0.4 * w, h * 0.8], fill=(200, 200, 210, 255))
    return img


class HatRenderer:
    '''帽子渲染:贴图加载/旋转/缩放缓存,兜底切换。
    锚定用「佩戴线」模式:.pivot 优先;未指定时自动检测——取贴图下部最宽一行的
    中心作为佩戴点(帽沿/帽底),该点对齐头上锚点,保证帽子"坐在"头上不悬空。'''

    def __init__(self):
        self.registry = load_registry()
        self._cache = {}
        self._pivot_cache = {}

    @staticmethod
    def _auto_pivot(im):
        '''佩戴线自动检测:下部 60% 内不透明像素最多的一行,取该行不透明段中心'''
        alpha = im.getchannel('A')
        w, h = im.size
        px = alpha.load()
        best_row, best_cnt, best_cx = h - 1, -1, w / 2.0
        y0 = int(h * 0.4)
        for y in range(y0, h):
            cnt = 0
            sx = 0.0
            for x in range(w):
                if px[x, y] > 60:
                    cnt += 1
                    sx += x
            if cnt > best_cnt:
                best_cnt = cnt
                best_row = y
                best_cx = sx / cnt if cnt else w / 2.0
        return (best_cx / w, (best_row + 1) / h)

    def _pivot_of(self, hat_id, im):
        pv = self.registry.get(hat_id, {}).get('pivot')
        if pv:
            return (float(pv[0]), float(pv[1]))
        if hat_id not in self._pivot_cache:
            self._pivot_cache[hat_id] = self._auto_pivot(im)
        return self._pivot_cache[hat_id]

    @staticmethod
    def _rot_point(p, c, angle_deg, src_size, dst_size):
        '''PIL rotate(angle, expand=True) 后,原坐标 p 的新坐标(视觉逆时针为正)'''
        A = math.radians(angle_deg)
        ca, sa = math.cos(A), math.sin(A)
        vx, vy = p[0] - c[0], p[1] - c[1]
        nx = ca * vx + sa * vy
        ny = -sa * vx + ca * vy
        d = ((dst_size[0] - src_size[0]) / 2.0, (dst_size[1] - src_size[1]) / 2.0)
        return (nx + c[0] + d[0], ny + c[1] + d[1])

    def get(self, hat_id, R, theta):
        '''返回 (旋转后贴图, pivot在贴图内的x, pivot在贴图内的y, 锚点x, 锚点y);失败返回 None'''
        meta = self.registry.get(hat_id)
        if meta is None:
            return None
        base = float(meta.get('base_offset_deg', 0))
        width = max(12, int(2 * R * float(meta.get('scale', 1.0))))
        theta_deg = round(math.degrees(theta)) % 360
        key = (hat_id, width, theta_deg)
        if key in self._cache:
            return self._cache[key]
        spr = load_hat_image(hat_id)
        if spr is None:
            spr = render_builtin_hat(meta.get('builtin_fallback', hat_id), width)
            pivot = tuple(meta.get('pivot', [0.5, 1.0]))
        else:
            ratio = spr.height / max(1, spr.width)
            spr = spr.resize((width, max(1, int(width * ratio))), Image.LANCZOS)
            pivot = self._pivot_of(hat_id, spr)
        # 旋转 1:按画稿基准角扶正;旋转 2:随头朝向
        spr1 = spr.rotate(-base, resample=Image.BICUBIC, expand=True)
        spr2 = spr1.rotate(-theta_deg, resample=Image.BICUBIC, expand=True)
        # 追踪 pivot 点
        c0 = (spr.width / 2.0, spr.height / 2.0)
        pt = (pivot[0] * spr.width, pivot[1] * spr.height)
        pt = self._rot_point(pt, c0, -base, spr.size, spr1.size)
        c1 = (spr1.width / 2.0, spr1.height / 2.0)
        pt = self._rot_point(pt, c1, -theta_deg, spr1.size, spr2.size)
        if len(self._cache) > 400:
            self._cache.clear()
        ax_, ay_ = tuple(meta.get('anchor', [0.0, -0.8]))
        out = (spr2, pt[0], pt[1], ax_, ay_)
        self._cache[key] = out
        return out
