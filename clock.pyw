# -*- coding: utf-8 -*-
"""A compact, resizable desktop clock; Python standard library only."""
import json
import os
import socket
import tkinter as tk
from tkinter import font as tkfont, messagebox
from datetime import datetime, timedelta, timezone

from clock_settings import (
    BASE_WIDTH, BASE_HEIGHT, DEFAULT_WIDTH, MIN_WIDTH, MAX_WIDTH,
    THEMES, normalize_state, clamp_position,
)
from window_layer import WindowLayer, enable_dpi_awareness

OFFSET_HOURS = 8
TZ_LABEL = "北京时间"
FONT_TIME = "Segoe UI Light"
FONT_SMALL = "Microsoft YaHei UI"
FONT_UTC = "Consolas"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "state.json")
ERROR_FILE = os.path.join(HERE, "error.log")
LOCK_PORT = 51789
WEEKDAYS = "一二三四五六日"
TRANSPARENT = "#010203"


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as stream:
            return normalize_state(json.load(stream))
    except (OSError, ValueError):
        return normalize_state({})


def save_state(data):
    try:
        temporary = STATE_FILE + ".tmp"
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, STATE_FILE)
    except OSError:
        pass


def acquire_single_instance():
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        connection.bind(("127.0.0.1", LOCK_PORT))
        connection.listen(1)
        return connection
    except OSError:
        connection.close()
        return None


class ClockCard:
    def __init__(self, root):
        self.root = root
        self.state = normalize_state(load_state())
        self.dpi = max(1.0, root.winfo_fpixels("1i") / 96)
        self.width = self.state["width"]
        self.theme = tk.StringVar(root, value=self.state["theme"])
        self.pinned = tk.BooleanVar(root, value=self.state["pinned"])
        self.layer_mode = tk.StringVar(root, value=self.state["layer"])
        self.drag = None
        self.resize_drag = None
        self.timer = None
        self.save_timer = None
        self.retry_timer = None
        self.closed = False
        self.fonts = {}
        root.title("真实时间")
        root.overrideredirect(True)
        root.configure(bg=THEMES[self.theme.get()]["bg"])
        self.transparent = False
        if os.name != "nt":
            try:
                root.attributes("-transparentcolor", TRANSPARENT)
                self.transparent = True
            except tk.TclError:
                pass
        self.canvas = tk.Canvas(root, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.draw()
        root.update_idletasks()
        self.layer = WindowLayer(root)
        self.layer.round_corners(self.px(BASE_WIDTH), self.px(BASE_HEIGHT), self.px(12))
        self.place(self.state["x"], self.state["y"])
        self.build_menu()
        self.bind_events()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.apply_layer(show_error=False)
        self.state.update(pid=os.getpid(),
                          started=datetime.now().isoformat(timespec="seconds"))
        self.persist()
        self.tick()

    @property
    def scale(self):
        return self.dpi * self.width / BASE_WIDTH

    def px(self, value):
        return round(value * self.scale)

    def coords(self, *values):
        return [self.px(v) for v in values]

    def round_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = (x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
                  x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
                  x1, y2, x1, y2-r, x1, y1+r, x1, y1)
        return self.canvas.create_polygon(*self.coords(*points), smooth=True,
                                           splinesteps=24, **kwargs)

    def text(self, x, y, value, family, size, color, anchor="w", **kwargs):
        key = family, size
        if key not in self.fonts:
            self.fonts[key] = tkfont.Font(self.root, family=family, size=-self.px(size))
        return self.canvas.create_text(*self.coords(x, y), text=value,
                                       font=self.fonts[key], fill=color, anchor=anchor, **kwargs)

    def draw(self):
        c = self.palette = THEMES[self.theme.get()]
        for (_, size), font in self.fonts.items():
            font.configure(size=-max(1, self.px(size)))
        self.canvas.delete("all")
        self.canvas.configure(width=self.px(BASE_WIDTH), height=self.px(BASE_HEIGHT),
                              bg=TRANSPARENT if self.transparent else c["bg"])
        self.root.configure(bg=c["bg"])
        line = max(1, self.px(0.7))
        self.round_rect(1, 1, 199, 111, 12, fill=c["bg"], outline=c["border"], width=line)
        self.canvas.create_oval(*self.coords(14, 16, 18, 20),
                                fill=c["accent"], outline="")
        self.text(24, 18, TZ_LABEL, FONT_SMALL, 10, c["muted"])
        self.time_item = self.text(12, 49, "00:00", FONT_TIME, 40, c["fg"])
        self.canvas.create_line(*self.coords(146, 42, 146, 61),
                                fill=c["border"], width=line)
        self.seconds_item = self.text(159, 52, "00", FONT_UTC, 19, c["accent"])
        self.date_item = self.text(15, 78, "", FONT_SMALL, 9.5, c["muted"])
        self.text(15, 96, "UTC", FONT_UTC, 8.5, c["muted"])
        self.utc_item = self.text(38, 96, "", FONT_UTC, 9, c["muted"])
        self.canvas.create_line(*self.coords(15, 106, 177, 106),
                                fill=c["track"], width=max(1, self.px(1.2)), capstyle="round")
        self.progress_item = self.canvas.create_line(*self.coords(15, 106, 15, 106),
                                                     fill=c["accent"],
                                                     width=max(1, self.px(1.2)), capstyle="round")
        # Pin and menu have comfortable click targets, with understated icons.
        pin_color = c["accent"] if self.pinned.get() else c["muted"]
        self.pin_hover = self.round_rect(144, 7, 168, 29, 6, fill=c["bg"],
                                         outline="", tags="pin")
        self.canvas.create_polygon(*self.coords(152, 11, 160, 11, 159, 17,
                                                162, 20, 150, 20, 153, 17),
                                   fill=pin_color if self.pinned.get() else "",
                                   outline=pin_color, width=line, tags="pin")
        self.canvas.create_line(*self.coords(156, 20, 156, 25),
                                fill=pin_color, width=line, tags="pin")
        self.menu_hover = self.round_rect(170, 7, 194, 29, 6, fill=c["bg"],
                                          outline="", tags="menu")
        for x in (178, 182, 186):
            self.canvas.create_oval(*self.coords(x-.7, 17.3, x+.7, 18.7),
                                    fill=c["muted"], outline="", tags="menu")
        self.canvas.create_rectangle(*self.coords(181, 92, 199, 111),
                                     fill=c["bg"], outline="", tags="resize")
        for a in (0, 4):
            self.canvas.create_line(*self.coords(187+a, 105, 195, 97+a),
                                    fill=c["border"], width=line, tags="resize")
        self.render_time(datetime.now(timezone.utc))

    def bind_events(self):
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_menu)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", self.on_leave)
        self.canvas.bind("<Control-MouseWheel>", self.on_wheel)

    def build_menu(self):
        if hasattr(self, "menu"):
            self.menu.destroy()
        c = self.palette
        options = dict(tearoff=0, bg=c["bg"], fg=c["fg"],
                       activebackground=c["track"], activeforeground=c["fg"],
                       selectcolor=c["accent"], bd=0, activeborderwidth=0,
                       font=(FONT_SMALL, 10))
        self.menu = tk.Menu(self.root, **options)
        self.menu.add_checkbutton(label="固定位置（Pin）", variable=self.pinned,
                                  command=self.toggle_pin)
        self.menu.add_separator()
        layers = tk.Menu(self.menu, **options)
        layers.add_radiobutton(label="始终悬浮在最上层", variable=self.layer_mode,
                               value="topmost", command=self.apply_layer)
        layers.add_radiobutton(label="始终仅悬浮在桌面层", variable=self.layer_mode,
                               value="desktop", command=self.apply_layer,
                               state="normal" if self.layer.available else "disabled")
        self.menu.add_cascade(label="显示层级", menu=layers)
        sizes = tk.Menu(self.menu, **options)
        for label, width in (("迷你 · 160", 160), ("精巧 · 192（默认）", 192),
                             ("舒展 · 240", 240), ("大号 · 320", 320)):
            sizes.add_command(label=label, command=lambda w=width: self.set_width(w))
        sizes.add_separator()
        sizes.add_command(label="拖动右下角 / Ctrl + 滚轮", state="disabled")
        self.menu.add_cascade(label="调整大小", menu=sizes)
        themes = tk.Menu(self.menu, **options)
        for group in ("浅色", "彩色", "深色"):
            if themes.index("end") is not None:
                themes.add_separator()
            themes.add_command(label=f"— {group} —", state="disabled")
            for key, theme in THEMES.items():
                if theme["group"] == group:
                    themes.add_radiobutton(label=theme["name"], variable=self.theme,
                                           value=key, command=self.change_theme)
        self.menu.add_cascade(label="外观主题", menu=themes)
        self.menu.add_separator()
        self.menu.add_command(label="退出时钟", command=self.close)

    def place(self, x, y):
        width, height = self.px(BASE_WIDTH), self.px(BASE_HEIGHT)
        area = self.layer.work_area(x, y, width, height)
        x, y = clamp_position(x, y, width, height, area)
        self.layer.move(x, y)
        return x, y

    def persist(self):
        if self.closed:
            return
        x, y, w, h = self.layer.rect()
        self.state.update(x=x, y=y, width=self.width, theme=self.theme.get(),
                          pinned=self.pinned.get(), layer=self.layer_mode.get(),
                          topmost=self.layer_mode.get() == "topmost", window=f"{w}x{h}")
        save_state(self.state)

    def queue_save(self):
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(250, self.finish_save)

    def finish_save(self):
        self.save_timer = None
        self.persist()

    def set_width(self, width, save=True):
        x, y, _, _ = self.layer.rect()
        width = max(MIN_WIDTH, min(MAX_WIDTH, round(width)))
        if self.pinned.get():
            area = self.layer.work_area(x, y)
            available = min((area[2] - x) / self.dpi,
                            (area[3] - y) / self.dpi * BASE_WIDTH / BASE_HEIGHT)
            width = min(width, max(MIN_WIDTH, int(available)))
        self.width = width
        self.draw()
        # Tk handles sizing; native positioning uses screen coordinates in both modes.
        self.root.geometry(f"{self.px(BASE_WIDTH)}x{self.px(BASE_HEIGHT)}")
        self.root.update_idletasks()
        self.layer.round_corners(self.px(BASE_WIDTH), self.px(BASE_HEIGHT), self.px(12))
        self.place(x, y)
        if save:
            self.queue_save()

    def toggle_pin(self):
        self.drag = None
        self.draw()
        self.persist()

    def change_theme(self):
        self.draw()
        # Rebuild after the native menu finishes processing its selection.
        self.root.after_idle(self.build_menu)
        self.persist()

    def apply_layer(self, show_error=True):
        if self.retry_timer:
            self.root.after_cancel(self.retry_timer)
            self.retry_timer = None
        try:
            self.layer.set_mode(self.layer_mode.get())
        except OSError as error:
            self.layer_mode.set(self.layer.mode)
            if show_error:
                messagebox.showwarning("暂时无法切换显示层级", str(error), parent=self.root)
            else:
                # A saved desktop preference may start before Explorer. Retry later.
                self.layer_mode.set("topmost")
                self.layer.set_mode("topmost")
                self.retry_timer = self.root.after(3000, self.retry_desktop)
        self.persist()

    def retry_desktop(self):
        self.retry_timer = None
        if self.closed:
            return
        self.layer_mode.set("desktop")
        self.apply_layer()

    def on_press(self, event):
        tags = self.canvas.gettags("current")
        if "menu" in tags:
            self.on_menu(event)
        elif "pin" in tags:
            self.pinned.set(not self.pinned.get())
            self.toggle_pin()
        elif "resize" in tags:
            self.resize_drag = (event.x_root, event.y_root, self.width)
            self.canvas.configure(cursor="size_nw_se")
        elif not self.pinned.get():
            x, y, _, _ = self.layer.rect()
            self.drag = (event.x_root - x, event.y_root - y)
            self.canvas.configure(cursor="fleur")

    def on_move(self, event):
        if self.resize_drag:
            x, y, start = self.resize_drag
            ratio = BASE_HEIGHT / BASE_WIDTH
            delta = ((event.x_root - x) + (event.y_root - y) * ratio) / (1 + ratio * ratio)
            self.set_width(start + delta / self.dpi, save=False)
        elif self.drag and not self.pinned.get():
            self.place(event.x_root - self.drag[0], event.y_root - self.drag[1])

    def on_release(self, _event):
        if self.drag or self.resize_drag:
            self.root.update_idletasks()
            self.persist()
        self.drag = self.resize_drag = None
        self.canvas.configure(cursor="")

    def on_wheel(self, event):
        if event.delta:
            self.set_width(self.width + (8 if event.delta > 0 else -8))
        return "break"

    def on_motion(self, _event):
        if self.drag or self.resize_drag:
            return
        tags = self.canvas.gettags("current")
        self.canvas.itemconfigure(self.pin_hover,
                                  fill=self.palette["track"] if "pin" in tags else self.palette["bg"])
        self.canvas.itemconfigure(self.menu_hover,
                                  fill=self.palette["track"] if "menu" in tags else self.palette["bg"])
        self.canvas.configure(cursor="size_nw_se" if "resize" in tags else
                              "hand2" if "pin" in tags or "menu" in tags else
                              "" if self.pinned.get() else "fleur")

    def on_leave(self, _event):
        self.canvas.itemconfigure(self.pin_hover, fill=self.palette["bg"])
        self.canvas.itemconfigure(self.menu_hover, fill=self.palette["bg"])

    def on_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def render_time(self, utc_now):
        local = utc_now.astimezone(timezone(timedelta(hours=OFFSET_HOURS)))
        self.canvas.itemconfigure(self.time_item, text=local.strftime("%H:%M"))
        self.canvas.itemconfigure(self.seconds_item, text=local.strftime("%S"))
        self.canvas.itemconfigure(self.date_item,
                                  text=f"{local:%Y / %m / %d}  ·  周{WEEKDAYS[local.weekday()]}")
        self.canvas.itemconfigure(self.utc_item, text=utc_now.strftime("%H:%M:%S"))
        elapsed = local.hour * 3600 + local.minute * 60 + local.second
        self.canvas.coords(self.progress_item, *self.coords(15, 106, 15 + 162 * elapsed / 86400, 106))
        self.canvas.itemconfigure(self.progress_item, state="normal" if elapsed else "hidden")

    def tick(self):
        if self.closed:
            return
        utc_now = datetime.now(timezone.utc)
        self.render_time(utc_now)
        try:
            self.layer.maintain()
        except OSError:
            # Keep the UI reachable if the desktop host becomes unavailable.
            self.layer_mode.set("topmost")
            self.layer.set_mode("topmost")
            self.persist()
        self.timer = self.root.after(max(20, 1000 - utc_now.microsecond // 1000), self.tick)

    def close(self):
        self.persist()
        self.closed = True
        for timer in (self.timer, self.save_timer, self.retry_timer):
            if timer:
                self.root.after_cancel(timer)
        self.layer.detach()
        self.root.destroy()


def main():
    lock = acquire_single_instance()
    if lock is None:
        return
    try:
        enable_dpi_awareness()
        root = tk.Tk()
        card = ClockCard(root)
        root.mainloop()
    finally:
        lock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        with open(ERROR_FILE, "w", encoding="utf-8") as stream:
            stream.write(traceback.format_exc())
        raise
