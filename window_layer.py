"""Windows desktop attachment, geometry, and monitor work areas.

Desktop mode makes only our own window a child of Explorer's existing desktop
host. We do not create WorkerW windows, move icons, or modify Explorer styles.
SetParent requires explicit WS_CHILD / WS_POPUP changes:
https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setparent
"""
import ctypes
from ctypes import wintypes as wt
import os


def enable_dpi_awareness():
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


class WindowLayer:
    def __init__(self, root):
        self.root = root
        self.mode = "topmost"
        self.host = None
        self.available = os.name == "nt"
        if not self.available:
            return
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        signatures = {
            "GetAncestor": ([wt.HWND, wt.UINT], wt.HWND),
            "GetParent": ([wt.HWND], wt.HWND),
            "GetWindowRect": ([wt.HWND, ctypes.POINTER(wt.RECT)], wt.BOOL),
            "SetParent": ([wt.HWND, wt.HWND], wt.HWND),
            "SetWindowPos": ([wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wt.UINT], wt.BOOL),
            "ScreenToClient": ([wt.HWND, ctypes.POINTER(wt.POINT)], wt.BOOL),
            "FindWindowExW": ([wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR], wt.HWND),
            "GetClassNameW": ([wt.HWND, wt.LPWSTR, ctypes.c_int], ctypes.c_int),
            "IsWindow": ([wt.HWND], wt.BOOL),
            "IsWindowVisible": ([wt.HWND], wt.BOOL),
            "SetWindowRgn": ([wt.HWND, wt.HRGN, wt.BOOL], ctypes.c_int),
            "MonitorFromRect": ([ctypes.POINTER(wt.RECT), wt.DWORD], wt.HANDLE),
            "GetMonitorInfoW": ([wt.HANDLE, ctypes.c_void_p], wt.BOOL),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = args, result
        suffix = "PtrW" if ctypes.sizeof(ctypes.c_void_p) == 8 else "W"
        self.get_style = getattr(self.api, "GetWindowLong" + suffix)
        self.get_style.argtypes = [wt.HWND, ctypes.c_int]
        self.get_style.restype = ctypes.c_ssize_t
        self.set_style = getattr(self.api, "SetWindowLong" + suffix)
        self.set_style.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
        self.set_style.restype = ctypes.c_ssize_t
        root.update_idletasks()
        self.hwnd = self.api.GetAncestor(root.winfo_id(), 2)
        self.original_style = self.get_style(self.hwnd, -16)

    def round_corners(self, width, height, radius):
        if not self.available:
            return
        # Native clipping also works for desktop child windows. Layered color-key
        # transparency can leave a child hit-testable but invisible in Explorer.
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        gdi.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        gdi.CreateRoundRectRgn.restype = wt.HRGN
        gdi.DeleteObject.argtypes = [wt.HANDLE]
        region = gdi.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius * 2, radius * 2)
        if not region:
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.api.SetWindowRgn(self.hwnd, region, True):
            gdi.DeleteObject(region)
            raise ctypes.WinError(ctypes.get_last_error())

    def desktop_host(self):
        found = []
        callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def visit(hwnd, _):
            name = ctypes.create_unicode_buffer(128)
            self.api.GetClassNameW(hwnd, name, len(name))
            if name.value in ("Progman", "WorkerW") and self.api.IsWindowVisible(hwnd):
                view = self.api.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
                if view:
                    # Use the desktop content view, not Progman itself: newer
                    # Explorer compositing can show GDI children of Progman black.
                    found.append(view)
            return True

        self.api.EnumWindows.argtypes = [callback_type, wt.LPARAM]
        self.api.EnumWindows.restype = wt.BOOL
        self.api.EnumWindows(callback_type(visit), 0)
        if not found:
            raise OSError("没有找到 Windows 桌面，请在资源管理器启动后重试。")
        return found[0]

    def rect(self):
        if self.available:
            rect = wt.RECT()
            if self.api.GetWindowRect(self.hwnd, ctypes.byref(rect)):
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        return (self.root.winfo_x(), self.root.winfo_y(),
                self.root.winfo_width(), self.root.winfo_height())

    def work_area(self, x, y, width=1, height=1):
        if self.available:
            class MonitorInfo(ctypes.Structure):
                _fields_ = [("size", wt.DWORD), ("monitor", wt.RECT),
                            ("work", wt.RECT), ("flags", wt.DWORD)]
            rect = wt.RECT(int(x), int(y), int(x + width), int(y + height))
            monitor = self.api.MonitorFromRect(ctypes.byref(rect), 2)
            info = MonitorInfo()
            info.size = ctypes.sizeof(info)
            if self.api.GetMonitorInfoW(monitor, ctypes.byref(info)):
                r = info.work
                return r.left, r.top, r.right, r.bottom
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def move(self, x, y):
        if not self.available:
            self.root.geometry(f"+{int(x)}+{int(y)}")
            return
        point = wt.POINT(int(x), int(y))
        if self.mode == "desktop" and self.host:
            self.api.ScreenToClient(self.host, ctypes.byref(point))
        # Do not activate the window or disturb its Z order when dragging.
        if not self.api.SetWindowPos(self.hwnd, None, point.x, point.y, 0, 0, 0x0015):
            raise ctypes.WinError(ctypes.get_last_error())

    def _parent(self, parent):
        ctypes.set_last_error(0)
        previous = self.api.SetParent(self.hwnd, parent)
        error = ctypes.get_last_error()
        if not previous and error:
            raise ctypes.WinError(error)

    def set_mode(self, mode):
        if mode == "desktop" and not self.available:
            raise OSError("桌面层模式仅支持 Windows。")
        if not self.available:
            self.root.attributes("-topmost", True)
            return
        x, y, _, _ = self.rect()
        if mode == "desktop":
            host = self.desktop_host()  # Resolve before altering the window.
            self.root.attributes("-topmost", False)
            try:
                self.set_style(self.hwnd, -16, (self.original_style & ~0x80000000) | 0x40000000)
                self._parent(host)
                if self.api.GetParent(self.hwnd) != host:
                    raise OSError("无法将时钟附着到桌面。")
                self.host, self.mode = host, "desktop"
                self.api.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, 0x0033)
                self.move(x, y)
            except OSError:
                self._parent(None)
                self.set_style(self.hwnd, -16, self.original_style)
                self.host, self.mode = None, "topmost"
                self.root.attributes("-topmost", True)
                self.move(x, y)
                raise
        else:
            if self.host:
                self._parent(None)
                self.set_style(self.hwnd, -16, self.original_style)
            self.host, self.mode = None, "topmost"
            self.root.attributes("-topmost", True)
            self.api.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0033)
            self.move(x, y)

    def maintain(self):
        if self.mode == "desktop" and self.available:
            if not self.api.IsWindow(self.host) or self.api.GetParent(self.hwnd) != self.host:
                self.set_mode("desktop")
        elif self.mode == "topmost":
            # Reapplying -topmost raises the clock over open native menus, even
            # when it is already topmost. Windows preserves this flag itself;
            # only repair it if it was actually lost, preserving popup Z order.
            is_topmost = (bool(self.get_style(self.hwnd, -20) & 0x00000008)
                          if self.available else bool(self.root.attributes("-topmost")))
            if not is_topmost:
                self.root.attributes("-topmost", True)

    def detach(self):
        if self.available and self.host and self.api.IsWindow(self.hwnd):
            self._parent(None)
            self.set_style(self.hwnd, -16, self.original_style)
            self.host = None
