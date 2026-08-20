#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_protocol.py
# Description: Contract tests for the Magic Home wire protocol
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.0
#
# Every REAL_* fixture below is a byte string captured from the live FVTLED /
# Zengge controller on 20-08-2026, not one composed to match the parser. A
# fixture built from an assumption only ever tests the assumption.

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "MagicHome.indigoPlugin", "Contents", "Server Plugin"))

import magichome_protocol as p    # noqa: E402


def hexb(text):
    return bytes.fromhex(text.replace(" ", ""))


# --- captured from the controller -----------------------------------------
REAL_OFF        = hexb("81 06 24 61 12 50 00 14 02 00 04 00 f0 78")
REAL_RED        = hexb("81 06 23 61 12 50 ff 00 00 00 04 00 f0 60")
REAL_WARM_WHITE = hexb("81 06 23 61 12 50 00 00 00 ff 04 00 0f 7f")
REAL_COOL_WHITE = hexb("81 06 23 61 12 50 ff ff ff 00 04 00 f0 5e")
REAL_PURPLE     = hexb("81 06 23 61 12 50 3a 00 3a 00 04 00 f0 d5")

# An unsolicited push frame, exactly as the controller emitted it. This is what
# desynchronised the first round of readings.
REAL_PUSH = hexb("b0 b1 b2 b3 00 02 02 4b 00 14 ea 81 01 00 06 04 23 61 01 50 "
                 "f0 40 64 08 00 00 02 00 00 00 12")

REAL_DISCOVERY = b"192.168.1.50,806A34112233,AK001-ZJ21413,1234ABCD-5678-90EF-1234-567890ABCDEF"


class TestFraming(unittest.TestCase):

    def test_checksum_is_a_plain_sum(self):
        self.assertEqual(p.checksum([0x71, 0x23, 0x0F]), 0xA3)

    def test_checksum_wraps_at_one_byte(self):
        self.assertEqual(p.checksum([0xFF, 0xFF]), 0xFE)

    def test_frame_appends_the_checksum(self):
        self.assertEqual(p.frame([0x71, 0x23, 0x0F]), hexb("71 23 0f a3"))


class TestPower(unittest.TestCase):

    def test_on_matches_the_bytes_that_worked(self):
        self.assertEqual(p.power(True), hexb("71 23 0f a3"))

    def test_off_matches_the_bytes_that_worked(self):
        self.assertEqual(p.power(False), hexb("71 24 0f a4"))

    def test_legacy_model_uses_the_pre_checksum_form(self):
        self.assertEqual(p.power(True, model_num=0x01), hexb("cc 23 33"))


class TestColour(unittest.TestCase):

    def test_red_matches_the_bytes_that_worked(self):
        self.assertEqual(p.colour(255, 0, 0), hexb("31 ff 00 00 00 f0 0f 2f"))

    def test_warm_white_matches_the_bytes_that_worked(self):
        self.assertEqual(p.warm_white(255), hexb("31 00 00 00 ff 0f 0f 4e"))

    def test_cool_white_on_rgbw_is_the_rgb_trio_at_full(self):
        # Measured from the app, not assumed: a model 0x06 has no second white.
        self.assertEqual(p.cool_white(255, model_num=0x06),
                         p.colour(255, 255, 255, model_num=0x06))

    def test_cool_white_on_rgbww_uses_the_second_white_channel(self):
        sent = p.cool_white(255, model_num=0x07)
        self.assertEqual(len(sent), 9)
        self.assertEqual(sent[5], 255)          # white2
        self.assertEqual(sent[1:5], bytes(4))   # RGB and warm white untouched

    def test_nine_byte_model_gets_nine_bytes(self):
        self.assertEqual(len(p.colour(1, 2, 3, 4, 5, model_num=0x25)), 9)

    def test_eight_byte_model_gets_eight_bytes(self):
        # A wrong length is not an error on the wire — it is a different
        # command. This is the single most damaging thing to get wrong.
        self.assertEqual(len(p.colour(1, 2, 3, 4, 5, model_num=0x06)), 8)

    def test_unknown_model_falls_back_to_eight_bytes(self):
        self.assertEqual(len(p.colour(1, 2, 3, model_num=0xEE)), 8)
        self.assertFalse(p.is_known_model(0xEE))

    def test_levels_are_clamped_not_wrapped(self):
        sent = p.colour(-40, 999, 12.6)
        self.assertEqual(sent[1], 0)
        self.assertEqual(sent[2], 255)
        self.assertEqual(sent[3], 13)

    def test_rubbish_levels_do_not_raise(self):
        self.assertEqual(p.colour(None, "", "green")[1:4], bytes(3))


class TestSpeed(unittest.TestCase):

    def test_delay_stays_in_the_controllers_range(self):
        for speed in range(-50, 200, 7):
            self.assertTrue(1 <= p.speed_to_delay(speed) <= p.MAX_DELAY)

    def test_fast_and_slow_are_the_right_way_round(self):
        self.assertLess(p.speed_to_delay(100), p.speed_to_delay(0))

    def test_round_trips_within_a_step(self):
        for speed in (0, 25, 50, 75, 100):
            self.assertLessEqual(abs(p.delay_to_speed(p.speed_to_delay(speed)) - speed), 4)

    def test_rubbish_delay_does_not_raise(self):
        self.assertEqual(p.delay_to_speed(None), 0)


class TestPresets(unittest.TestCase):

    def test_every_preset_builds(self):
        for code in p.PRESETS:
            sent = p.preset(code, 50)
            self.assertEqual(sent[0], 0x61)
            self.assertEqual(sent[1], code)
            self.assertEqual(sent[-1], p.checksum(sent[:-1]))

    def test_the_codes_are_the_documented_contiguous_block(self):
        self.assertEqual(sorted(p.PRESETS), list(range(0x25, 0x39)))

    def test_an_invalid_pattern_is_refused_loudly(self):
        with self.assertRaises(ValueError):
            p.preset(0x99)


class TestCustomPattern(unittest.TestCase):

    def test_lead_byte_marks_only_the_first_colour(self):
        sent = p.custom_pattern([(255, 0, 0), (0, 255, 0)])
        self.assertEqual(sent[0], 0x51)
        self.assertEqual(sent[4], 0x00)

    def test_empty_slots_are_padded_with_the_firmware_sentinel(self):
        sent = p.custom_pattern([(255, 0, 0)])
        self.assertEqual(sent[4:8], bytes([0x00, 0x01, 0x02, 0x03]))

    def test_more_than_sixteen_colours_is_truncated_not_refused(self):
        sent = p.custom_pattern([(1, 1, 1)] * 30)
        self.assertEqual(len(sent), p.CUSTOM_PATTERN_SLOTS * 4 + 6)

    def test_no_colours_is_refused(self):
        with self.assertRaises(ValueError):
            p.custom_pattern([])

    def test_transition_styles_map_to_their_bytes(self):
        for name, code in p.TRANSITIONS.items():
            self.assertEqual(p.custom_pattern([(1, 2, 3)], transition=name)[-4], code)

    def test_unknown_transition_falls_back_to_gradual(self):
        self.assertEqual(p.custom_pattern([(1, 2, 3)], transition="disco")[-4],
                         p.TRANSITION_GRADUAL)


class TestStateParsing(unittest.TestCase):

    def test_off_frame(self):
        s = p.parse_state(REAL_OFF)
        self.assertIsNotNone(s)
        self.assertFalse(s.is_on)
        self.assertEqual(s.model_num, 0x06)
        self.assertEqual(s.brightness_percent, 0)

    def test_red_frame(self):
        s = p.parse_state(REAL_RED)
        self.assertTrue(s.is_on)
        self.assertEqual(s.rgb, (255, 0, 0))
        self.assertEqual(s.white, 0)
        self.assertEqual(s.brightness_percent, 100)

    def test_warm_white_frame_is_flagged_as_white_mode(self):
        s = p.parse_state(REAL_WARM_WHITE)
        self.assertTrue(s.is_white_mode)
        self.assertEqual(s.white, 255)
        self.assertEqual(s.brightness_percent, 100)

    def test_cool_white_frame_is_rgb_not_white(self):
        # The whole point: the app's cool white is RGB at full.
        s = p.parse_state(REAL_COOL_WHITE)
        self.assertFalse(s.is_white_mode)
        self.assertEqual(s.rgb, (255, 255, 255))
        self.assertEqual(s.white, 0)

    def test_purple_frame_brightness_uses_the_strongest_channel(self):
        s = p.parse_state(REAL_PURPLE)
        self.assertEqual(s.brightness_percent, 23)

    def test_speed_is_none_outside_preset_mode(self):
        # A number that means nothing reads as a measurement.
        self.assertIsNone(p.parse_state(REAL_RED).speed)

    def test_speed_is_reported_while_a_preset_runs(self):
        raw = bytearray(REAL_RED)
        raw[3] = 0x25                       # seven colour cross fade
        raw[5] = 0x01                       # fastest
        raw[13] = p.checksum(raw[:13])
        s = p.parse_state(bytes(raw))
        self.assertTrue(s.is_preset)
        self.assertEqual(s.preset_name, "Seven colour cross fade")
        self.assertEqual(s.speed, 100)

    def test_a_corrupt_checksum_is_rejected(self):
        raw = bytearray(REAL_RED)
        raw[13] ^= 0xFF
        self.assertIsNone(p.parse_state(bytes(raw)))

    def test_a_wrong_header_is_rejected(self):
        raw = bytearray(REAL_RED)
        raw[0] = 0x82
        raw[13] = p.checksum(raw[:13])
        self.assertIsNone(p.parse_state(bytes(raw)))

    def test_a_short_frame_is_rejected(self):
        self.assertIsNone(p.parse_state(REAL_RED[:9]))

    def test_none_is_rejected(self):
        self.assertIsNone(p.parse_state(None))


class TestFrameScanning(unittest.TestCase):

    def test_finds_the_frame_behind_an_unsolicited_push(self):
        s = p.find_state_frame(REAL_PUSH + REAL_COOL_WHITE)
        self.assertIsNotNone(s)
        self.assertEqual(s.rgb, (255, 255, 255))

    def test_finds_the_frame_ahead_of_a_push(self):
        s = p.find_state_frame(REAL_RED + REAL_PUSH)
        self.assertIsNotNone(s)
        self.assertEqual(s.rgb, (255, 0, 0))

    def test_prefers_the_newest_of_several(self):
        s = p.find_state_frame(REAL_RED + REAL_COOL_WHITE)
        self.assertEqual(s.rgb, (255, 255, 255))

    def test_model_filter_skips_a_frame_from_the_wrong_model(self):
        other = bytearray(REAL_RED)
        other[1] = 0x33
        other[13] = p.checksum(other[:13])
        s = p.find_state_frame(REAL_COOL_WHITE + bytes(other), expect_model=0x06)
        self.assertEqual(s.rgb, (255, 255, 255))

    def test_pure_noise_yields_nothing(self):
        self.assertIsNone(p.find_state_frame(b"\x00" * 40))

    def test_empty_buffer_yields_nothing(self):
        self.assertIsNone(p.find_state_frame(b""))


class TestDiscovery(unittest.TestCase):

    def test_parses_the_real_reply(self):
        d = p.parse_discovery_reply(REAL_DISCOVERY)
        self.assertEqual(d.ip, "192.168.1.50")
        self.assertEqual(d.mac, "806A34112233")
        self.assertEqual(d.hardware_id, "AK001-ZJ21413")

    def test_the_app_name_is_the_mac_tail_not_a_model(self):
        d = p.parse_discovery_reply(REAL_DISCOVERY)
        self.assertTrue(d.name.startswith("112233"))

    def test_a_reply_without_the_uuid_still_parses(self):
        d = p.parse_discovery_reply("192.168.1.50,AABBCCDDEEFF,AK001-ZJ200")
        self.assertEqual(d.mac, "AABBCCDDEEFF")

    def test_rubbish_is_rejected_rather_than_half_parsed(self):
        for junk in (b"", b"hello", b"1.2.3.4", b",,"):
            self.assertIsNone(p.parse_discovery_reply(junk))

    def test_mac_normalises_to_a_stable_key(self):
        self.assertEqual(p.normalise_mac("80:6a:34:11:22:33"), "806A34112233")
        self.assertEqual(p.normalise_mac("80-6A-34-11-22-33"), "806A34112233")
        self.assertEqual(p.normalise_mac(None), "")


class TestModelTable(unittest.TestCase):

    def test_the_live_controller_is_recognised(self):
        m = p.model_for(0x06)
        self.assertEqual(m.channels, "RGBW")
        self.assertEqual(m.msg_len, 8)
        self.assertFalse(m.has_two_whites)

    def test_rgbww_models_declare_two_whites(self):
        for num in (0x07, 0x25, 0x35):
            self.assertTrue(p.model_for(num).has_two_whites)

    def test_an_rgb_only_model_declares_no_white(self):
        self.assertFalse(p.model_for(0x33).has_white)


if __name__ == "__main__":
    unittest.main(verbosity=2)
