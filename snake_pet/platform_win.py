'''Win32 封装层 —— 窗口/分层更新/钩子/互斥/注册表自启/度量/屏幕采样。
本模块不得出现游戏逻辑(P0 纪律);所有句柄资源的申请/释放成对提供。'''
import ctypes
import logging
import os
import sys
from ctypes import wintypes

from .constants import APP_NAME, AUTOSTART_NAME, RUN_KEY

WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 513
WM_RBUTTONDOWN = 516
WM_QUIT = 18
WS_EX_LAYERED = 524288
WS_EX_TOOLWINDOW = 128
WS_EX_NOACTIVATE = 134217728
WS_EX_TOPMOST = 8
WS_POPUP = 0x80000000
WS_VISIBLE = 268435456
ULW_ALPHA = 2
GA_ROOT = 2
PM_REMOVE = 1
SPI_GETWORKAREA = 48
SM_CXSCREEN = 0
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = (76, 77)
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = (78, 79)
ERROR_ALREADY_EXISTS = 183
HWND_BOTTOM = 1
HWND_NOTOPMOST = -2
SWP_FLAGS = 0x16  # SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
SRCCOPY = 13369376

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ('pt', wintypes.POINT),
        ('mouseData', wintypes.DWORD),
        ('flags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', ctypes.c_long),
        ('biHeight', ctypes.c_long),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', ctypes.c_long),
        ('biYPelsPerMeter', ctypes.c_long),
        ('biClrUsed', ctypes.c_int),
        ('biClrImportant', ctypes.c_int),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ('BlendOp', wintypes.BYTE),
        ('BlendFlags', wintypes.BYTE),
        ('SourceConstantAlpha', wintypes.BYTE),
        ('AlphaFormat', wintypes.BYTE),
    ]


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
    ]


_BLEND = BLENDFUNCTION(0, 0, 255, 1)
_mutex_handle = None

# ---- 函数原型 ----
psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, wintypes.DWORD]
user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = ctypes.c_void_p
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC,
    ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE),
    wintypes.HDC, ctypes.POINTER(wintypes.POINT),
    wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
kernel32.CreateMutexW.restype = ctypes.c_void_p
kernel32.GetModuleHandleW.restype = ctypes.c_void_p


def ensure_dpi_aware():
    '''进程 DPI 感知(Per-Monitor V2 失败则退回系统级)'''
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        user32.SetProcessDPIAware()


# v5 使用独立互斥名:与 v4 原版 exe 可并存运行,便于 P0 黑盒行为对照
MUTEX_NAME = APP_NAME + '_v5_Mutex_V1'


def acquire_single_instance_mutex():
    '''单实例互斥;已存在实例时返回 False(静默退出)。句柄保持进程生命周期'''
    global _mutex_handle
    _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    exists = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
    if exists:
        return False
    return True


def create_layered_window(title, w, h, topmost=False):
    '''创建分层工具窗口(不激活);topmost 仅菜单窗口使用'''
    hinst = kernel32.GetModuleHandleW(None)
    ex = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if topmost:
        ex |= WS_EX_TOPMOST
    hwnd = user32.CreateWindowExW(ex, 'STATIC', title, WS_POPUP | WS_VISIBLE,
                                  0, 0, w, h, None, None, hinst, None)
    return hwnd


def sink_window_bottom(hwnd):
    '''沉底显示:被任何应用窗口覆盖,回到桌面才可见(v5 设计不变量)'''
    user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_FLAGS)


def untopmost_window(hwnd):
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_FLAGS)


def show_window(hwnd, cmd):
    user32.ShowWindow(hwnd, cmd)


def destroy_window(hwnd):
    user32.DestroyWindow(hwnd)


def window_from_point(x, y):
    return user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))


def get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, buf, 64)
    return buf.value


def is_window_visible(hwnd):
    return bool(user32.IsWindowVisible(hwnd))


def get_window_ex_style(hwnd):
    return user32.GetWindowLongW(hwnd, -20)


def get_window_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def enum_topmost_layered_windows():
    '''枚举全部顶层窗口,返回 (hwnd, ex, rect) 列表(避让/看门狗逻辑由调用方裁决)'''
    results = []

    def cb(hwnd, _):
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        results.append((hwnd, get_window_ex_style(hwnd),
                        (r.left, r.top, r.right, r.bottom)))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return results


def virtual_screen():
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    return (vx, vy, vw, vh)


def primary_screen_metric():
    return user32.GetSystemMetrics(SM_CXSCREEN)


def workarea():
    rect = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return (rect.left, rect.top, rect.right, rect.bottom)


def is_desktop_window(hwnd):
    '''点击目标是否为桌面(Progman/WorkerW 系)'''
    return get_class_name(hwnd) in ('Progman', 'WorkerW', 'SHELLDLL_DefView', 'SysListView32')


def grab_screen_bgra(x, y, w, h):
    '''抓取屏幕 (x, y) 起 w×h 区域的 BGRA 字节(看门狗像素检测用);失败返回 None'''
    hdcs = user32.GetDC(0)
    if not hdcs:
        return None
    hdcm = gdi32.CreateCompatibleDC(hdcs)
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bits = ctypes.c_void_p()
    hb = gdi32.CreateDIBSection(hdcm, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
    data = None
    if hb:
        old = gdi32.SelectObject(hdcm, hb)
        gdi32.BitBlt(hdcm, 0, 0, w, h, hdcs, x, y, SRCCOPY)
        data = ctypes.string_at(bits, w * h * 4)
        gdi32.SelectObject(hdcm, old)
        gdi32.DeleteObject(hb)
    gdi32.DeleteDC(hdcm)
    user32.ReleaseDC(0, hdcs)
    return data


def blit_image_to_window(hwnd, img, x, y):
    '''把 PIL RGBA 图像一次性推送到指定分层窗口(菜单用;DC/BMP 即用即毁)'''
    (w, h) = img.size
    buf = img.tobytes('raw', 'BGRA')
    hdc = gdi32.CreateCompatibleDC(0)
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bits = ctypes.c_void_p()
    hb = gdi32.CreateDIBSection(hdc, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
    if not hb:
        gdi32.DeleteDC(hdc)
        return False
    old = gdi32.SelectObject(hdc, hb)
    ctypes.memmove(bits, buf, len(buf))
    pt = wintypes.POINT(int(x), int(y))
    sz = wintypes.SIZE(w, h)
    src = wintypes.POINT(0, 0)
    ok = bool(user32.UpdateLayeredWindow(hwnd, 0, ctypes.byref(pt), ctypes.byref(sz),
                                         hdc, ctypes.byref(src), 0, ctypes.byref(_BLEND), ULW_ALPHA))
    gdi32.SelectObject(hdc, old)
    gdi32.DeleteObject(hb)
    gdi32.DeleteDC(hdc)
    return ok


def working_set_mb():
    '''当前进程工作集(MB, soak 内存统计用);失败返回 -1'''
    try:
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(pmc)
        if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(),
                                      ctypes.byref(pmc), ctypes.sizeof(pmc)):
            return pmc.WorkingSetSize / (1024 * 1024)
    except Exception as e:
        logging.debug('读取进程内存失败: %r', e)
    return -1.0


def autostart_command():
    '''开机自启命令行:打包 exe 用自身路径;源码运行用 pythonw + 仓库根 run_pet.py'''
    if getattr(sys, 'frozen', False):
        return '"%s"' % sys.executable
    exe = sys.executable
    pw = os.path.join(os.path.dirname(exe), 'pythonw.exe')
    if not os.path.exists(pw):
        pw = exe
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(os.path.dirname(pkg_dir), 'run_pet.py')
    return f'"{pw}" "{script}"'


def set_autostart(enabled):
    '''设置开机自启动(HKCU Run 键, 键名 SnakePet)'''
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            if enabled:
                winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, autostart_command())
            else:
                winreg.DeleteValue(key, AUTOSTART_NAME)
            key.Close()
            return True
        except FileNotFoundError:
            key.Close()
            raise
    except Exception as e:
        logging.warning('设置开机自启动失败: %r', e)
    return False
