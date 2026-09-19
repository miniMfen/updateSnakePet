'''pytest 全局夹具:每个测试使用独立的 SNAKEPET_HOME,
避免测试的存档/配置写入仓库根(污染用户真实宠物数据)。'''
import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    home = tmp_path / 'snakepet_home'
    home.mkdir(exist_ok=True)
    monkeypatch.setenv('SNAKEPET_HOME', str(home))
    yield
