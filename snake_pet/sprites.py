'''贴图加载与缓存(snake_head / apple / cap;P4 扩 hats)'''
import logging
import os
import sys

from PIL import Image, ImageStat

from .config import base_dir


def sprite_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'sprites')
    return os.path.join(base_dir(), 'sprites')


def load_sprite(name):
    p = os.path.join(sprite_dir(), name)
    try:
        if os.path.exists(p):
            im = Image.open(p).convert('RGBA')
            logging.info('已加载贴图 %s (%dx%d)', name, im.width, im.height)
            return im
        return None
    except Exception as e:
        logging.warning('贴图 %s 加载失败: %r', name, e)
        return None


def load_cap_sprite():
    '''加载睡帽贴图并裁掉四周透明边距(只留帽子内容, 位置/缩放才准确)'''
    im = load_sprite('cap.png')
    if im is None:
        return None
    try:
        bb = im.getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox()
        if bb:
            im = im.crop(bb)
        logging.info('睡帽贴图内容区域: %s', bb)
        return im
    except Exception as e:
        logging.warning('睡帽贴图裁剪失败: %r', e)
        return im


def load_snake_sprite():
    '''按优先级加载蛇贴图(用于提取配色)'''
    for name in ('snake_apple_512.png', 'snake_noto_emoji_512.png', 'snake_openmoji_618.png',
                 'snake_twemoji_72.png', 'snake.png', 'snake_head.png'):
        im = load_sprite(name)
        if im is None:
            continue
        return (im, name)
    return (None, None)


def sprite_dominant(im):
    '''取贴图不透明像素的平均主色(给蛇身/蛇头配色)'''
    rgb = im.convert('RGB')
    mask = im.getchannel('A').point(lambda v: 255 if v > 40 else 0)
    st = ImageStat.Stat(rgb, mask)
    return (int(st.mean[0]), int(st.mean[1]), int(st.mean[2]))
