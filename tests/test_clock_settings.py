"""Preference migration and geometry regressions; no GUI or dependencies."""
import unittest
from clock_settings import normalize_state, clamp_position, height_for_width


class PreferencesTests(unittest.TestCase):
    def test_first_upgrade_shrinks_without_losing_position(self):
        state = normalize_state({"x": 1549, "y": 86, "topmost": True,
                                 "window": "332x206"})
        self.assertEqual((state["x"], state["y"], state["width"]), (1549, 86, 192))
        self.assertEqual(state["layer"], "topmost")
        self.assertLess(state["width"] * height_for_width(state["width"]), 332 * 206 / 3)

    def test_old_non_topmost_migrates_to_desktop(self):
        self.assertEqual(normalize_state({"topmost": False})["layer"], "desktop")

    def test_saved_choices_override_legacy_flag(self):
        raw = {"layer": "desktop", "topmost": True, "theme": "paper",
               "width": 240, "pinned": True, "x": -1500, "y": 42}
        state = normalize_state(raw)
        for key, value in raw.items():
            self.assertEqual(state[key], value)

    def test_malformed_settings_have_safe_defaults(self):
        for raw in (None, [], "oops", {"width": float("nan"), "theme": [],
                                     "x": None, "y": "bad", "layer": {}, "pinned": "false"}):
            state = normalize_state(raw)
            self.assertEqual(state["width"], 192)
            self.assertEqual(state["theme"], "graphite")
            self.assertEqual(state["layer"], "topmost")
            self.assertFalse(state["pinned"])

    def test_size_limits_and_nonfinite_values(self):
        for value, expected in ((-99, 144), (9999, 480), (float("inf"), 192), ("224", 224)):
            self.assertEqual(normalize_state({"width": value})["width"], expected)

    def test_negative_monitor_coordinates_are_preserved(self):
        self.assertEqual(clamp_position(-1800, 120, 192, 108, (-1920, 0, 0, 1040)),
                         (-1800, 120))

    def test_taskbar_and_disconnected_monitor_recovery(self):
        self.assertEqual(clamp_position(1900, 1070, 192, 108, (0, 0, 1920, 1040)),
                         (1728, 932))
        self.assertEqual(clamp_position(-1800, -600, 192, 108, (0, 0, 1920, 1040)),
                         (0, 0))


if __name__ == "__main__":
    unittest.main()
