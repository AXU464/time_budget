"""Clock preferences and palettes, independent of the window system."""
import math

BASE_WIDTH, BASE_HEIGHT = 200, 112
DEFAULT_WIDTH, MIN_WIDTH, MAX_WIDTH = 192, 144, 480
THEMES = {
    "graphite": dict(name="石墨 · Graphite", group="深色", bg="#1b211f", fg="#f0eee6",
                     muted="#a5aea6", accent="#b3cbb4", border="#39443e", track="#303b34"),
    "paper": dict(name="雾白 · Paper", group="浅色", bg="#f4f3ed", fg="#313d39",
                  muted="#617067", accent="#47725f", border="#d5ddd4", track="#e3e7de"),
    "midnight": dict(name="钴蓝 · Cobalt", group="彩色", bg="#1947a3", fg="#f6f7ff",
                     muted="#c0d2f3", accent="#ffd48a", border="#5274b7", track="#3f63ab"),
    "sand": dict(name="暖砂 · Sand", group="浅色", bg="#eee5d6", fg="#54473b",
                 muted="#756451", accent="#89582f", border="#d9cbb8", track="#dfd1be"),
    "plum": dict(name="莓酒 · Berry", group="深色", bg="#51243d", fg="#fae9e4",
                 muted="#d8b2c0", accent="#ffbf9e", border="#81516a", track="#703e57"),
    "glacier": dict(name="冰川 · Glacier", group="浅色", bg="#e4f2f8", fg="#23485c",
                    muted="#526f80", accent="#206d8b", border="#b6d3df", track="#c8e0ea"),
    "mint": dict(name="青瓷 · Celadon", group="浅色", bg="#e4f0df", fg="#254331",
                 muted="#536c56", accent="#36704f", border="#bdceba", track="#ccddc7"),
    "sakura": dict(name="樱花 · Sakura", group="浅色", bg="#fae6eb", fg="#653d50",
                   muted="#885569", accent="#b13f69", border="#e4bdca", track="#efd0da"),
    "lavender": dict(name="藤萝 · Wisteria", group="浅色", bg="#eee7fa", fg="#4d3a69",
                     muted="#716083", accent="#8050ac", border="#cebee4", track="#ddd0ee"),
    "butter": dict(name="奶油 · Butter", group="浅色", bg="#f9efb8", fg="#584a20",
                   muted="#7a682e", accent="#875017", border="#dacc8d", track="#e9dca0"),
    "silver": dict(name="银灰 · Silver", group="浅色", bg="#e5e9ee", fg="#202834",
                   muted="#596576", accent="#465b7b", border="#bdc6d1", track="#cdd5df"),
    "terracotta": dict(name="赤陶 · Terracotta", group="彩色", bg="#a84330", fg="#fff5e9",
                       muted="#ffe2cf", accent="#ffe59b", border="#cf7d65", track="#bd6650"),
    "lagoon": dict(name="碧湾 · Lagoon", group="彩色", bg="#136b69", fg="#effbf4",
                   muted="#c1e4d7", accent="#f6da87", border="#4a9490", track="#37817d"),
    "terminal": dict(name="荧光 · Terminal", group="深色", bg="#101715", fg="#c3f7c9",
                     muted="#8bac95", accent="#b4f34b", border="#385244", track="#2c3d32"),
}


def bounded_number(value, default, low, high):
    try:
        value = float(value)
        if not math.isfinite(value):
            return default
        return max(low, min(value, high))
    except (TypeError, ValueError, OverflowError):
        return default


def normalize_state(raw):
    state = dict(raw) if isinstance(raw, dict) else {}
    state["width"] = round(bounded_number(state.get("width"), DEFAULT_WIDTH,
                                          MIN_WIDTH, MAX_WIDTH))
    if not isinstance(state.get("theme"), str) or state["theme"] not in THEMES:
        state["theme"] = "graphite"
    if state.get("layer") not in ("topmost", "desktop"):
        state["layer"] = "desktop" if state.get("topmost") is False else "topmost"
    state["pinned"] = state.get("pinned") is True
    for key in ("x", "y"):
        state[key] = round(bounded_number(state.get(key), 80, -100000, 100000))
    return state


def height_for_width(width):
    return round(width * BASE_HEIGHT / BASE_WIDTH)


def clamp_position(x, y, width, height, work_area):
    left, top, right, bottom = work_area
    return (max(left, min(int(x), right - width)),
            max(top, min(int(y), bottom - height)))
