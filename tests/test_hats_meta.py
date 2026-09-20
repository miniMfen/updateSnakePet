'''头饰元数据回归测试 —— 佩戴线不丢 / 两份真源一致 / 画稿朝向正确。

[v5.2 回归背景]
1) `load_registry()` 原先用 `merged.update(data)` 做**整条替换**。sprites/hats/hats.json
   里 7 顶帽子都没写 `pivot` → DEFAULT_REGISTRY 里逐顶标定好的佩戴线被整条丢掉,
   全部退回自动检测。即**精心校准过的佩戴线从未生效**。
2) 夜帽/圣诞的 `base_offset_deg` 原来是 35 / 30,但两者画稿本来就是正立的,
   这个偏移是无依据的额外旋转 → 真机上帽子顺时针歪过去、帽沿斜切过脸、后脑勺空着。
3) 皇冠 scale=0.82 是 7 顶里最小的(渲染高度仅约其他帽的 60%),且佩戴点偏低。

本文件把这些钉成不变量。
'''
import json
import os

import pytest

from snake_pet import hats as hm
from snake_pet.hats import DEFAULT_REGISTRY, HAT_IDS, hats_dir, load_registry


def test_json_overrides_default_fields():
    '''hats.json 给出的字段覆盖默认值,未给出的字段(如 pivot)必须保留'''
    reg = load_registry()
    for hid in HAT_IDS:
        assert hid in reg
    # pivot 是 DEFAULT 专有字段(hats.json 不写),必须存活
    for hid in ('nightcap', 'santa', 'graduation', 'tophat', 'cap_blue', 'bowknot'):
        assert reg[hid].get('pivot') == DEFAULT_REGISTRY[hid]['pivot'], (
            '%s 的 pivot 被整条替换丢掉了:%s' % (hid, reg[hid].get('pivot')))


def test_json_pivot_preserved_when_json_omits_it(tmp_path, monkeypatch):
    '''构造一份"只有 anchor、没有 pivot"的 hats.json,验证 pivot 不丢'''
    (tmp_path / 'hats.json').write_text(
        json.dumps({'santa': {'name': '圣诞', 'anchor': [0.0, -0.99], 'scale': 1.3}},
                   ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(hm, 'hats_dir', lambda: str(tmp_path))
    reg = load_registry()
    assert reg['santa']['anchor'] == [0.0, -0.99]          # json 覆盖
    assert reg['santa']['scale'] == 1.3                    # json 覆盖
    assert reg['santa']['pivot'] == DEFAULT_REGISTRY['santa']['pivot']   # 默认保留
    assert reg['santa']['base_offset_deg'] == DEFAULT_REGISTRY['santa']['base_offset_deg']


def test_shipped_hats_json_matches_default_registry():
    '''ship 的 sprites/hats/hats.json 与 DEFAULT_REGISTRY 必须逐字段一致(消除第二份真源)。

    注意:不能用 hats_dir() —— 它走 base_dir(),而测试夹具把 SNAKEPET_HOME 指到临时目录,
    那里没有 hats.json,会静默 SKIP 掉本检查(等于没跑,已实测)。
    这里直接按包路径定位仓库里 ship 的那份文件。
    '''
    root = os.path.dirname(os.path.dirname(os.path.abspath(hm.__file__)))
    p = os.path.join(root, 'sprites', 'hats', 'hats.json')
    assert os.path.isfile(p), '仓库里找不到 ship 的 hats.json: %s' % p
    data = json.load(open(p, encoding='utf-8'))
    for hid, meta in data.items():
        assert hid in DEFAULT_REGISTRY, 'hats.json 有未知帽 id %r' % hid
        for k, v in meta.items():
            d = DEFAULT_REGISTRY[hid].get(k)
            assert d == v, 'hats.json 与 DEFAULT_REGISTRY 不一致:%s.%s = %r vs %r' % (
                hid, k, v, d)
    # 反向:默认表里声明的锚点字段也必须出现在 json 中(避免只在兜底里生效)
    for hid in ('nightcap', 'santa', 'crown'):
        for k in ('anchor', 'scale', 'base_offset_deg'):
            assert k in data[hid], '%s 的 %s 只写在 DEFAULT_REGISTRY 里,未落到 hats.json' % (hid, k)


def test_upright_hat_artworks_have_zero_base_offset():
    '''画稿本身正立的帽子不得有额外基准旋转(歪戴的根因)'''
    reg = load_registry()
    for hid in ('nightcap', 'santa', 'crown'):
        assert float(reg[hid]['base_offset_deg']) == 0, (
            '%s 的 base_offset_deg=%s —— 其画稿是正立的,额外旋转会让帽沿斜切过脸'
            % (hid, reg[hid]['base_offset_deg']))


def test_crown_size_and_height_comparable_to_others():
    '''皇冠不得明显小于其他帽子,且要戴在头顶(锚点足够高)'''
    reg = load_registry()
    c = reg['crown']
    others = [reg[k]['scale'] for k in ('tophat', 'santa', 'graduation', 'cap_blue')]
    assert float(c['scale']) >= min(others) * 0.95, (
        '皇冠 scale=%s 明显小于其他帽 %s' % (c['scale'], others))
    assert float(c['anchor'][1]) <= -0.98, (
        '皇冠 anchor_y=%s 偏低,会显得卡在脸上而不是戴在头顶' % c['anchor'][1])


def test_wearing_line_aligns_to_anchor(monkeypatch, tmp_path):
    '''佩戴线(pivot)必须真的被使用:同一帽子换 pivot 会改变贴图上的对齐点'''
    monkeypatch.setattr(hm, 'hats_dir', lambda: str(tmp_path))
    hr = hm.HatRenderer()
    a = hr.get('santa', 17.0, 0.0)
    assert a is not None
    hr2 = hm.HatRenderer()
    hr2.registry['santa'] = dict(hr2.registry['santa'])
    hr2.registry['santa']['pivot'] = [0.5, 0.5]     # 故意改成图中点
    hr2._cache.clear()
    b = hr2.get('santa', 17.0, 0.0)
    assert (a[1], a[2]) != (b[1], b[2]), 'pivot 未生效(对齐点没变)'
