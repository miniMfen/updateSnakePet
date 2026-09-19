'''仓库根启动器:双击/pythonw 直接运行,注册开机自启也指向本文件'''
import sys

sys.path.insert(0, __import__('os').path.dirname(__file__))

from snake_pet.__main__ import cli

if __name__ == '__main__':
    sys.exit(cli(sys.argv[1:]))
