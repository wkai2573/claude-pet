"""多螢幕支援：查詢某個座標所在螢幕的工作區（扣掉工作列）。

Tk 的 winfo_screenwidth()／winfo_screenheight() 只回傳主螢幕的大小，拿它來限制位置，
視窗就只能待在主螢幕；這裡改用 Windows 的 MonitorFromPoint／GetMonitorInfo，
每個螢幕各自算（副螢幕在左邊或上面時，座標會是負的，這也沒問題）。
"""
import ctypes
from ctypes import wintypes


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


MONITOR_DEFAULTTONEAREST = 2


def work_area(x, y):
    """包含 (x, y) 的螢幕工作區 (左, 上, 右, 下)；點不在任何螢幕上就取最近的那個。查不到回傳 None。"""
    try:
        user32 = ctypes.windll.user32
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MonitorInfo)]
        mon = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), MONITOR_DEFAULTTONEAREST)
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return None
        r = info.rcWork
        return (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None


def area_for(root, x, y):
    """work_area，查不到時退回「主螢幕整個畫面」。"""
    return work_area(x, y) or (0, 0, root.winfo_screenwidth(), root.winfo_screenheight())


def primary_area(root):
    return work_area(0, 0) or (0, 0, root.winfo_screenwidth(), root.winfo_screenheight())

