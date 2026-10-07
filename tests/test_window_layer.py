"""Keep clock refreshes from changing native popup menu Z order."""
import unittest
from unittest.mock import Mock
from window_layer import WindowLayer


class LayerMaintenanceTests(unittest.TestCase):
    def layer(self, topmost):
        layer = WindowLayer.__new__(WindowLayer)
        layer.mode = "topmost"
        layer.available = True
        layer.hwnd = 123
        layer.root = Mock()
        layer.get_style = Mock(return_value=0x80 | (0x8 if topmost else 0))
        return layer

    def test_refresh_does_not_raise_clock_over_popups(self):
        layer = self.layer(True)
        for _ in range(5):
            layer.maintain()
        layer.root.attributes.assert_not_called()

    def test_lost_topmost_is_repaired_once(self):
        layer = self.layer(False)
        layer.maintain()
        layer.root.attributes.assert_called_once_with("-topmost", True)
        layer.get_style.return_value |= 0x8
        layer.maintain()
        layer.root.attributes.assert_called_once_with("-topmost", True)

    def test_desktop_mode_is_not_promoted(self):
        layer = self.layer(False)
        layer.mode = "desktop"
        layer.host = 456
        layer.api = Mock()
        layer.api.IsWindow.return_value = True
        layer.api.GetParent.return_value = layer.host
        layer.maintain()
        layer.root.attributes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
