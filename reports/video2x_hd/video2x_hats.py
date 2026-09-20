# -*- coding: utf-8 -*-
'''帽子素材 video2x 两遍超分管线(RGB 一遍 + alpha 遮罩一遍,合并回 RGBA)

video2x 的 realesrgan 处理器只走 3 通道,直接喂 RGBA 会把 alpha 拍平。
方案:先把 alpha 导出为灰度 RGB 图,与"颜色外溢(bled)"后的 RGB 分别用
video2x 超分 4 倍,再把超分 alpha 贴回超分 RGB,得到 4 倍 RGBA。
用法:
  python video2x_hats.py prep   # 生成 _rgb/_alpha 中间图
  python video2x_hats.py upscale [model]  # 对中间图逐个跑 video2x
  python video2x_hats.py merge  # 合并到 stage/ 目录
'''
import os
import subprocess
import sys

from PIL import Image, ImageFilter

BASE = r'D:/aiWorkCode/professionalWork/updateSnakePet'
SRC_DIR = os.path.join(BASE, 'sprites', 'hats')
WORK = os.path.join(BASE, 'reports', 'video2x_hd', 'work')
STAGE = os.path.join(BASE, 'reports', 'video2x_hd', 'stage')
EXE = r'D:/windowTools/video2x/video2x/build/video2x_win64/video2x.exe'
MODEL = 'realesrgan-plus-anime'
HATS = ['bowknot', 'cap_blue', 'crown', 'graduation', 'nightcap', 'santa', 'tophat']


def prep():
    os.makedirs(WORK, exist_ok=True)
    for name in HATS:
        im = Image.open(os.path.join(SRC_DIR, name + '.png')).convert('RGBA')
        rgb = im.convert('RGB')
        a = im.getchannel('A')
        blur = rgb.filter(ImageFilter.GaussianBlur(6))
        bled = Image.composite(rgb, blur, a)  # 不透明区保原色,透明区用邻域色外溢填充
        a_rgb = Image.merge('RGB', (a, a, a))
        bled.save(os.path.join(WORK, f'{name}_rgb.png'))
        a_rgb.save(os.path.join(WORK, f'{name}_alpha.png'))
        print(f'prep {name}: {im.size}')


def upscale(model):
    os.makedirs(WORK, exist_ok=True)
    for name in HATS:
        for kind in ('rgb', 'alpha'):
            src = os.path.join(WORK, f'{name}_{kind}.png')
            dst = os.path.join(WORK, f'{name}_{kind}_x4.png')
            if os.path.exists(dst):
                os.remove(dst)
            cmd = [EXE, '-i', src, '-o', dst, '-p', 'realesrgan', '-s', '4',
                   '--realesrgan-model', model, '-d', '1',
                   '-c', 'png', '--pix-fmt', 'rgba', '--no-progress']
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            ok = os.path.exists(dst) and open(dst, 'rb').read(8) == b'\x89PNG\r\n\x1a\n'
            # 退出码 0xC0000005(3221225477)为本机已知"成功后收尾崩溃",以产物为准
            tag = 'OK' if ok else 'FAIL'
            print(f'[{tag}] {name}_{kind} rc={r.returncode}')
            if not ok:
                print(r.stdout[-800:])
                print(r.stderr[-800:])
                sys.exit(1)


def merge():
    os.makedirs(STAGE, exist_ok=True)
    for name in HATS:
        src = Image.open(os.path.join(SRC_DIR, name + '.png')).convert('RGBA')
        w, h = src.size
        rgb_up = Image.open(os.path.join(WORK, f'{name}_rgb_x4.png')).convert('RGB')
        a_up = Image.open(os.path.join(WORK, f'{name}_alpha_x4.png')).convert('L')
        assert rgb_up.size == (w * 4, h * 4), f'{name} 尺寸异常 {rgb_up.size} != {(w*4, h*4)}'
        out = rgb_up.convert('RGBA')
        out.putalpha(a_up)
        dst_path = os.path.join(STAGE, name + '.png')
        out.save(dst_path)
        aa = out.getchannel('A').getextrema()
        px = out.load()
        corners = [px[0, 0][3], px[out.width - 1, 0][3], px[0, out.height - 1][3], px[out.width - 1, out.height - 1][3]]
        print(f'merge {name}: {out.size} alpha范围={aa} 四角={corners}')


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if action == 'prep':
        prep()
    elif action == 'upscale':
        upscale(sys.argv[2] if len(sys.argv) > 2 else MODEL)
    elif action == 'merge':
        merge()
    elif action == 'all':
        prep()
        upscale(MODEL)
        merge()
