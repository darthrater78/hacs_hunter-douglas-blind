"""Protocol tests. Load the pure-Python package directly so no Home Assistant
install is needed (CI runs `python3 -m unittest discover tests`)."""

import importlib.util
import sys
import unittest
from pathlib import Path

_PKG = Path(__file__).parent.parent / "custom_components/hacs_hunter_douglas_blind/protocol"
_spec = importlib.util.spec_from_file_location(
    "pv_protocol", _PKG / "__init__.py", submodule_search_locations=[str(_PKG)]
)
pv = importlib.util.module_from_spec(_spec)
sys.modules["pv_protocol"] = pv
_spec.loader.exec_module(pv)


class AdvertisementTest(unittest.TestCase):
    def test_real_duette_tdbu_payload(self):
        # Sniffed from real hardware 2026-09-17 (see docs/PROTOCOL.md §2).
        adv = pv.parse_advertisement(bytes.fromhex("3CF8080000090000C0"))
        self.assertEqual(adv.home_id, 63548)
        self.assertEqual(adv.type_id, 8)
        self.assertEqual(adv.primary, 0.0)
        self.assertAlmostEqual(adv.secondary, 0.225)
        self.assertEqual(adv.tilt, 0.0)
        self.assertEqual(adv.velocity, 192)

    def test_real_duette_tdbu_moved_payload(self):
        # Raw scan from the Android app on 2026-09-21: primary raw 0x3000
        # (clamps to 100%), secondary 250/40 = 6.25%, status byte 0xC0.
        adv = pv.parse_advertisement(bytes.fromhex("3CF80800" "30FA0000C0"))
        self.assertEqual(adv.home_id, 63548)
        self.assertEqual(adv.primary, 100.0)
        self.assertAlmostEqual(adv.secondary, 6.25)
        self.assertEqual(adv.tilt, 0.0)
        self.assertEqual(adv.velocity, 192)

    def test_short_payload_omits_optional_fields(self):
        adv = pv.parse_advertisement(bytes.fromhex("3CF8081027"))
        self.assertEqual(adv.primary, 100.0)
        self.assertIsNone(adv.secondary)

    def test_too_short_returns_none(self):
        self.assertIsNone(pv.parse_advertisement(b"\x00\x01"))


class FrameTest(unittest.TestCase):
    def test_primary_only_layout(self):
        frame = pv.build_command_frame(5, primary=50)
        self.assertEqual(len(frame), 13)
        self.assertEqual(frame.hex(), "f7010509881300800080008000")

    def test_tilt_marker(self):
        frame = pv.build_command_frame(0, tilt=40)
        self.assertEqual(frame[10:12], bytes([40, 0x00]))

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            pv.build_command_frame(0, primary=101)


class CapabilityTest(unittest.TestCase):
    def test_duette_tdbu_has_two_rails(self):
        cap, known = pv.capability_for_type(8)
        self.assertTrue(known)
        self.assertTrue(cap.primary and cap.secondary and not cap.tilt)

    def test_unknown_type_falls_back(self):
        cap, known = pv.capability_for_type(250)
        self.assertFalse(known)
        self.assertEqual(cap.name, "bottom_up")

    def test_venetian_tilt(self):
        cap, _ = pv.capability_for_type(51)
        self.assertEqual(cap.tilt_range_degrees, 180)


if __name__ == "__main__":
    unittest.main()
