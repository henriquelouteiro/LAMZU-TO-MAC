"""Drives the desktop UI in demo mode (no hardware) and checks the bytes that
reach the device. Skipped when PySide6 is not installed."""
import os
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

from lamzu_mac import protocol as P

FLASH = (Path(__file__).parent / "fixtures" / "flash_f510.bin").read_bytes()


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class GuiFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from lamzu_mac.gui.app import MainWindow
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow(FLASH)
        cls.pump(1.5)
        cls.perf, cls.buttons, cls.lighting, cls.sensor, cls.device = cls.win.pages

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    @classmethod
    def pump(cls, seconds=0.5):
        end = time.time() + seconds
        while time.time() < end:
            cls.app.processEvents()
            time.sleep(0.01)

    def flash(self) -> P.FlashImage:
        self.pump()
        return P.FlashImage(bytes(self.win.worker.device.flash))

    def choose(self, category: str, index: int):
        b = self.buttons
        b._select(index)
        b.category.setCurrentIndex(b.category.findData(category))
        b._show_category()

    def test_loads_device(self):
        self.assertEqual(self.win.state, "online")
        img = self.win.image
        self.assertEqual(self.perf.big_dpi.text(), f"{img.dpi_stage(img.setting('dpi-active')).dpi} DPI")

    def test_polling_rate(self):
        self.perf.rate._buttons[4000].click()
        self.assertEqual(P.REPORT_RATES[self.flash().setting("report-rate")], 4000)

    def test_dpi_stages(self):
        self.perf._set_count(3)
        self.perf.rows[1].spin.setValue(2400)
        self.perf.rows[1]._commit()
        self.perf.rows[1].radio.click()
        f = self.flash()
        self.assertEqual((f.setting("dpi-stages"), f.dpi_stage(1).dpi, f.setting("dpi-active")), (3, 2400, 1))

    def test_media_key(self):
        self.choose("media", 4)
        self.buttons.sub["media"].setCurrentIndex(self.buttons.sub["media"].findData("vol-up"))
        self.buttons._apply()
        self.assertEqual(P.format_shortcut(self.flash().shortcut(4)), "vol-up")

    def test_captured_shortcut(self):
        self.choose("shortcut", 3)
        mods = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        self.buttons.capture.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_T, mods))
        self.buttons._apply()
        expected = "Cmd+Shift+T" if os.sys.platform == "darwin" else "Ctrl+Shift+T"
        self.assertEqual(P.format_shortcut(self.flash().shortcut(3)), expected)

    def test_left_click_is_protected(self):
        self.choose("disabled", 0)
        self.buttons._apply()
        self.assertEqual(self.flash().binding(0).describe(), "left")
        self.assertTrue(self.buttons.warning.isVisibleTo(self.buttons))

    def test_lighting(self):
        lt = self.lighting
        lt.bar_mode.setCurrentIndex(lt.bar_mode.findData(2))
        lt.bar_color.set_rgb((0, 128, 255))
        lt._commit_bar("x")
        lt.dpi_effect.setCurrentIndex(lt.dpi_effect.findData(2))
        lt._commit_dpi_effect()
        f = self.flash()
        self.assertEqual((f.led_bar().mode, f.led_bar().color, f.setting("led-bar-enable")),
                         (2, (0, 128, 255), 1))
        self.assertEqual((f.setting("dpi-led-enable"), f.setting("dpi-led-mode")), (1, 2))

    def test_model_capabilities(self):
        # demo identity: Atlantis Mini (no LEDs per the official config) on a 4K receiver
        self.assertEqual(self.win.dev_name.text(), "Atlantis Mini")
        visible = [hz for hz, b in self.perf.rate._buttons.items() if not b.isHidden()]
        self.assertEqual(visible, [125, 250, 500, 1000, 2000, 4000])
        self.assertTrue(self.win.nav_buttons["lighting"].isHidden())

    def test_unknown_model_shows_everything(self):
        dev = self.win.worker.device
        dev.identify = lambda: P.Identity(P.LAMZU_CID, 42, 1)
        try:
            self.win.reload()
            self.pump(1.0)
            self.assertFalse(self.win.nav_buttons["lighting"].isHidden())
            self.assertFalse(self.win.banner.isHidden())
        finally:
            del dev.identify
            self.win.reload()
            self.pump(1.0)

    def test_sensor(self):
        if not self.sensor.toggles["motion-sync"].isChecked():
            self.sensor.toggles["motion-sync"].click()
        self.sensor.lod._buttons[3].click()
        self.sensor.debounce.committed.emit(6)
        f = self.flash()
        self.assertEqual((f.setting("motion-sync"), f.setting("lod"), f.setting("debounce")), (1, 3, 6))


if __name__ == "__main__":
    unittest.main()
