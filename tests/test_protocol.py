"""Protocol tests. Vectors come from a LAMZU 4K Receiver (pid 0xF510, firmware
1.24) and from constants recovered from HIDUsb.dll; see docs/PROTOCOL.md."""
import unittest
from pathlib import Path

from lamzu_mac import protocol as P

FLASH = (Path(__file__).parent / "fixtures" / "flash_f510.bin").read_bytes()


class ReportTests(unittest.TestCase):
    def test_version_request_matches_native_layout(self):
        self.assertEqual(P.build_report(P.Cmd.READ_VERSION).hex(" "),
                         "08 12 00 00 00 00 00 00 00 00 00 00 00 00 00 00 3b")

    def test_parse_captured_replies(self):
        version = P.parse_report(bytes.fromhex("0812000000020124000000000000000014"))
        self.assertEqual((version.payload[0], version.payload[1]), (0x01, 0x24))
        battery = P.parse_report(bytes.fromhex("080400000002" "1e000e5f" + "00" * 6 + "bc"))
        self.assertEqual(battery.payload[:4], bytes([30, 0, 0x0E, 0x5F]))

    def test_bad_checksum_rejected(self):
        with self.assertRaises(P.ProtocolError):
            P.parse_report(bytes.fromhex("0812000000020124000000000000000015"))

    def test_flash_reads_are_chunked_by_ten(self):
        reqs = P.read_flash_requests(0x00, 0xC0)
        self.assertEqual(len(reqs), 20)
        self.assertEqual(reqs[1][3:6], bytes([0x00, 0x0A, 0x0A]))
        self.assertEqual(reqs[-1][3:6], bytes([0x00, 0xBE, 0x02]))

    def test_flash_writes_are_chunked_by_ten(self):
        reqs = P.write_flash_requests(0x100, bytes(range(13)))
        self.assertEqual([r[5] for r in reqs], [10, 3])
        self.assertEqual(reqs[1][3:9], bytes([0x01, 0x0A, 0x03, 10, 11, 12]))


class DpiCodecTests(unittest.TestCase):
    def test_roundtrip_full_range(self):
        for dpi in range(P.DPI_MIN, P.DPI_MAX + 1, P.DPI_STEP):
            x, y, ex = P.encode_dpi(dpi)
            self.assertEqual(x, y)
            self.assertEqual(P.decode_dpi(x, ex), dpi)

    def test_known_values(self):
        self.assertEqual(P.encode_dpi(1600), (0x1F, 0x1F, 0x00))
        self.assertEqual(P.encode_dpi(26000), (0x07, 0x07, 0x88))

    def test_rejects_off_step(self):
        with self.assertRaises(ValueError):
            P.encode_dpi(1625)


class FlashImageTests(unittest.TestCase):
    def setUp(self):
        self.img = P.FlashImage(FLASH)

    def test_captured_settings(self):
        self.assertEqual(P.REPORT_RATES[self.img.setting("report-rate")], 1000)
        self.assertEqual(self.img.setting("dpi-stages"), 1)
        self.assertEqual(self.img.setting("dpi-active"), 0)
        self.assertEqual(self.img.setting("led-off-time"), 6)
        self.assertEqual(self.img.setting("peak-time"), 3)
        self.assertIn(self.img.setting("lod"), P.LOD_VALUES)

    def test_captured_dpi_stages(self):
        dpis = [self.img.dpi_stage(i).dpi for i in range(8)]
        self.assertEqual(dpis, [1600, 1600, 400, 3200, 6400, 6400, 6400, 6400])
        self.assertEqual(self.img.dpi_stage(0).color, (0x00, 0xFF, 0xFF))

    def test_captured_buttons(self):
        names = [self.img.binding(i).describe() for i in range(8)]
        self.assertEqual(names, ["left", "right", "middle", "back", "forward",
                                 "dpi-cycle", "dpi-up", "dpi-down"])

    def test_captured_led_bar(self):
        self.assertEqual(self.img.led_bar(), P.LedBar(1, (0xFF, 0, 0), 7, 9))

    def test_set_dpi_patch(self):
        patch = self.img.set_dpi(0, 800)
        self.assertEqual(patch, P.Patch(0x0C, bytes([0x0F, 0x0F, 0x00, 0x37])))
        self.assertEqual(self.img.dpi_stage(0).dpi, 800)
        req = P.patch_requests([patch])[0]
        self.assertEqual(req.hex(" "), "08 07 00 00 0c 04 0f 0f 00 37 00 00 00 00 00 00 e1")

    def test_set_pair_matches_serializer(self):
        # ProtocolDataUpdate writes [value, 0x55 - value] with length 2.
        req = P.patch_requests([self.img.set_setting("report-rate", 0x20)])[0]
        self.assertEqual(req[:8], bytes([0x08, 0x07, 0x00, 0x00, 0x00, 0x02, 0x20, 0x35]))

    def test_captured_extra_bindings(self):
        # 0x80..0x8B in the dump: rate switch, LED effect cycle, fire 10 ms x3
        self.assertEqual(self.img.binding(8).describe(), "rate-cycle")
        self.assertEqual(self.img.binding(9).describe(), "light-effect-cycle")
        self.assertEqual(self.img.binding(10).describe(), "fire:10:3")

    def test_dpi_lock_matches_official_table(self):
        self.assertEqual(P.parse_binding("dpi-lock:100"), P.Binding(P.KeyClass.DPI_LOCK, 1))
        self.assertEqual(P.parse_binding("dpi-lock:1200").param1, 0x17)
        self.assertEqual(P.Binding(P.KeyClass.DPI_LOCK, 0x0F).describe(), "dpi-lock:800")

    def test_fire_ranges(self):
        with self.assertRaises(ValueError):
            P.parse_binding("fire:5:1")
        with self.assertRaises(ValueError):
            P.parse_binding("fire:10:4")

    def test_binding_patch(self):
        patch = self.img.set_binding(3, P.parse_binding("dpi-up"))
        self.assertEqual(patch, P.Patch(0x6C, bytes([0x02, 0x02, 0x00, 0x51])))


class IdentityTests(unittest.TestCase):
    def test_identify_request_layout(self):
        req = P.identify_request(bytes([0x6A, 0x3A, 0x6A, 0xF5]))
        self.assertEqual(req.hex(" "), "08 01 00 00 00 08 6a 3a 6a f5 00 00 00 00 00 00 41")

    def test_captured_reply_is_atlantis_mini_on_4k(self):
        reply = P.parse_report(bytes.fromhex("0801000000 08 afe0333e 0b0201 000000 36".replace(" ", "")))
        ident = P.parse_identity(reply)
        self.assertEqual((ident.cid, ident.mid, ident.device_type), (11, 2, 1))
        self.assertEqual(ident.model.name, "Atlantis Mini")
        self.assertEqual(ident.rates(), [125, 250, 500, 1000, 2000, 4000])

    def test_rate_is_limited_by_mouse_and_link(self):
        self.assertEqual(P.Identity(11, 5, 5).max_rate, 4000)   # Paro on an 8K receiver
        self.assertEqual(P.Identity(11, 1, 5).max_rate, 8000)   # OG V2 on an 8K receiver
        self.assertEqual(P.Identity(11, 1, 0).max_rate, 1000)   # OG V2 on a 1K receiver

    def test_unknown_models(self):
        self.assertIsNone(P.Identity(11, 42, 1).model)
        self.assertFalse(P.Identity(7, 2, 1).is_lamzu)
        self.assertIsNone(P.Identity(7, 2, 1).model)

    def test_8k_code(self):
        self.assertEqual(P.REPORT_RATE_CODES[8000], 0x40)


class ShortcutTests(unittest.TestCase):
    def test_cmd_c(self):
        events = P.parse_shortcut("cmd+c")
        self.assertEqual(events, [(0x80, 0, 0x08), (0x80, 1, 0x06), (0x40, 1, 0x06), (0x40, 0, 0x08)])
        buf = P.encode_shortcut(events)
        self.assertEqual(buf[0], 4)
        self.assertEqual(buf[1:4], bytes([0x80, 0x08, 0x00]))
        self.assertEqual(P.decode_shortcut(buf + bytes(8)), events)

    def test_media_key(self):
        buf = P.encode_shortcut(P.parse_shortcut("mute"))
        self.assertEqual(buf[:7], bytes([2, 0x82, 0xE2, 0x00, 0x42, 0xE2, 0x00]))

    def test_format_shortcut(self):
        self.assertEqual(P.format_shortcut(P.parse_shortcut("ctrl+shift+t")), "Ctrl+Shift+T")
        self.assertEqual(P.format_shortcut(P.parse_shortcut("vol-up")), "vol-up")

    def test_shortcut_binds_button(self):
        img = P.FlashImage(FLASH)
        patches = img.set_shortcut(4, P.parse_shortcut("f5"))
        self.assertEqual(patches[0].address, 0x100 + 4 * 0x20)
        self.assertEqual(img.binding(4), P.Binding(P.KeyClass.SHORTCUT))


if __name__ == "__main__":
    unittest.main()
