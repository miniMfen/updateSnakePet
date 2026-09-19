'''SnakePet v5 —— Windows 桌面贪吃蛇宠物(纯 Win32 + PIL/UpdateLayeredWindow)

v4 基线重建包(P0), 模块划分:
  constants     常量表(与 00_BASELINE §12 逐一对应)
  config        配置读写与版本迁移
  platform_win  Win32 封装(窗口/DIB/钩子/互斥/注册表/度量), 不含游戏逻辑
  sprites       贴图加载与缓存
  snake         蛇运动学(path/pos/move/_wander/_chase/_ok)
  fx            特效粒子与老化
  behavior      状态机(饱食度/心情/睡觉/空闲小动作/进食反应)
  render        整帧 PIL 绘制(蛇/食物/夜帽/气泡/菜单面板), 不碰 Win32 句柄
  menu          菜单布局/命中/回调
  app           SnakePet 组装: 窗口/钩子线程/事件队列/主循环/看门狗 + CLI 三件套
'''

__version__ = '5.1.0'
APP_NAME = 'SnakePet'
