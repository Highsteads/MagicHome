#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_plugin.py
# Description: Contract tests for the MagicHome Indigo plugin
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.0

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "MagicHome.indigoPlugin",
                                "Contents", "Server Plugin"))

import indigo_stub                                    # noqa: E402
indigo_stub.install()

import plugin as plug                                 # noqa: E402
import magichome_protocol as proto                    # noqa: E402
from indigo_stub import FakeAction, FakeDevice        # noqa: E402


def hexb(text):
    return bytes.fromhex(text.replace(" ", ""))


REAL_RED  = proto.parse_state(hexb("81 06 23 61 12 50 ff 00 00 00 04 00 f0 60"))
REAL_WHITE = proto.parse_state(hexb("81 06 23 61 12 50 00 00 00 ff 04 00 0f 7f"))


class FakeController(object):
    def __init__(self, ip="192.168.1.50", ok=True, state=REAL_RED):
        self.ip         = ip
        self.model_num  = 0x06
        self.name       = "fake"
        self.last_state = state
        self.last_error = "unreachable"
        self.sent       = []
        self.ok         = ok
        self.calls      = []

    def send(self, payload, force=False):
        self.sent.append(bytes(payload))
        return self.ok

    def read_state(self, force=False):
        return self.last_state

    def turn_on(self):
        self.calls.append("on")
        return self.ok

    def turn_off(self):
        self.calls.append("off")
        return self.ok

    def set_colour(self, r, g, b, white=None):
        self.calls.append(("colour", r, g, b, white))
        return self.ok

    def set_warm_white(self, level):
        self.calls.append(("warm", level))
        return self.ok

    def set_cool_white(self, level=255):
        self.calls.append(("cool", level))
        return self.ok

    def set_preset(self, pattern, speed=50):
        self.calls.append(("preset", pattern, speed))
        return self.ok

    def set_custom_pattern(self, colours, speed=50, transition="gradual"):
        self.calls.append(("custom", tuple(colours), speed, transition))
        return self.ok

    def close(self):
        pass


def make_plugin(prefs=None):
    return plug.Plugin("com.clives.indigoplugin.magichome", "MagicHome", "1.0.0",
                       prefs if prefs is not None else {})


def wire(plugin, dev, controller=None, state=REAL_RED):
    controller = controller or FakeController(state=state)
    plugin.store["controllers"][dev.id] = controller
    plugin.store["effects"][dev.id]     = _NullRunner()
    plugin.store["next_poll"][dev.id]   = 0.0
    return controller


def call_of(controller, kind):
    """First structured call of a given kind. The code sends the colour and
    then an explicit on, so the last call is not the interesting one."""
    for entry in controller.calls:
        if isinstance(entry, tuple) and entry[0] == kind:
            return entry
    return None


class _NullRunner(object):
    name    = ""
    running = False

    def stop(self, wait=True, timeout=3.0):
        return True

    def start(self, name, steps, on_finish=None):
        self.name = name
        return True


class TestCoercion(unittest.TestCase):
    """Indigo hands every saved dialog field back as a string, so nothing
    arriving from a dialog may be used as a number without a guarded convert."""

    def test_a_numeric_string_converts(self):
        self.assertEqual(plug.as_int("30"), 30)

    def test_a_blank_field_falls_back_instead_of_raising(self):
        self.assertEqual(plug.as_int("", 15), 15)

    def test_text_in_a_number_field_falls_back(self):
        self.assertEqual(plug.as_int("fifteen", 15), 15)
        self.assertEqual(plug.as_float("soon", 5.0), 5.0)

    def test_none_falls_back(self):
        self.assertEqual(plug.as_int(None, 7), 7)

    def test_bounds_are_applied(self):
        self.assertEqual(plug.as_int("500", 0, 0, 100), 100)
        self.assertEqual(plug.as_int("-50", 0, 0, 100), 0)

    def test_percent_and_byte_round_trip(self):
        for percent in (0, 25, 50, 100):
            self.assertLessEqual(abs(plug.to_percent(plug.to_byte(percent)) - percent), 1)


class TestDurationWording(unittest.TestCase):

    def test_short_spans_are_said_in_seconds(self):
        # "0 minute" is a number that means nothing.
        self.assertEqual(plug.describe_span(12), "12 second")

    def test_medium_spans_are_said_in_minutes(self):
        self.assertEqual(plug.describe_span(900), "15 minute")

    def test_long_spans_are_said_in_hours(self):
        self.assertEqual(plug.describe_span(7200), "2.0 hour")

    def test_rubbish_does_not_raise(self):
        self.assertEqual(plug.describe_span(None), "0 second")


class TestPaletteParsing(unittest.TestCase):

    def test_a_normal_palette(self):
        self.assertEqual(plug.parse_palette("255,0,0 / 0,255,0"),
                         [(255, 0, 0), (0, 255, 0)])

    def test_spaces_and_semicolons_are_accepted(self):
        self.assertEqual(plug.parse_palette("255 0 0; 0 0 255"),
                         [(255, 0, 0), (0, 0, 255)])

    def test_a_broken_entry_is_skipped_not_turned_into_black(self):
        # A stray blank would otherwise show as a blackout mid-fade.
        self.assertEqual(plug.parse_palette("255,0,0 / / 0,0,255"),
                         [(255, 0, 0), (0, 0, 255)])

    def test_out_of_range_values_are_clamped(self):
        self.assertEqual(plug.parse_palette("999,-4,0"), [(255, 0, 0)])

    def test_rubbish_yields_nothing_rather_than_a_wrong_colour(self):
        self.assertEqual(plug.parse_palette("red, green, blue"), [])
        self.assertEqual(plug.parse_palette(""), [])
        self.assertEqual(plug.parse_palette(None), [])


class TestHueCache(unittest.TestCase):

    def test_a_dim_colour_normalises_to_its_hue(self):
        self.assertEqual(plug.Plugin._normalise_hue((64, 0, 64)), (255, 0, 255))

    def test_black_does_not_divide_by_zero(self):
        self.assertEqual(plug.Plugin._normalise_hue((0, 0, 0)), (255, 255, 255))

    def test_a_full_colour_is_unchanged(self):
        self.assertEqual(plug.Plugin._normalise_hue((255, 128, 0)), (255, 128, 0))


class TestPublishing(unittest.TestCase):

    def test_a_reading_reaches_the_device_states(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p._publish(dev, REAL_RED, ctrl)
        self.assertTrue(dev.states["onOffState"])
        self.assertEqual(dev.states["redLevel"], 100)
        self.assertEqual(dev.states["mode"], "Colour")
        self.assertTrue(dev.states["online"])

    def test_no_answer_is_recorded_as_unknown_never_as_off(self):
        # An unanswered query means "I do not know". Writing it as off would
        # invent a reading nobody took, and a dead controller would look like
        # a light somebody switched off.
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        dev.states["onOffState"] = True
        dev.states["online"] = True
        p._publish(dev, None, ctrl)
        self.assertFalse(dev.states["online"])
        self.assertEqual(dev.states["mode"], "unknown")
        self.assertTrue(dev.states["onOffState"], "on/off must be left alone, not invented")
        self.assertEqual(dev.errorState, "offline")

    def test_white_mode_is_labelled_as_white(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev, state=REAL_WHITE)
        p._publish(dev, REAL_WHITE, ctrl)
        self.assertEqual(dev.states["mode"], "White")
        self.assertEqual(dev.states["whiteLevel"], 100)

    def test_a_running_preset_is_named(self):
        raw = bytearray(REAL_RED.raw)
        raw[3] = 0x38
        raw[13] = proto.checksum(raw[:13])
        state = proto.parse_state(bytes(raw))
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p._publish(dev, state, ctrl)
        self.assertEqual(dev.states["mode"], "Pattern: Seven colour jumping")

    def test_recovery_clears_the_error_state(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p._publish(dev, None, ctrl)
        p._publish(dev, REAL_RED, ctrl)
        self.assertEqual(dev.errorState, "")


class TestBrightness(unittest.TestCase):

    def test_dimming_keeps_the_hue(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p.store["hue"][dev.id] = (255, 0, 255)
        p._set_brightness(dev, 20)
        self.assertEqual(call_of(ctrl, "colour"), ("colour", 51, 0, 51, None))
        self.assertEqual(dev.states["brightnessLevel"], 20)

    def test_zero_brightness_turns_it_off(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p._set_brightness(dev, 0)
        self.assertIn("off", ctrl.calls)
        self.assertFalse(dev.states["onOffState"])

    def test_dimming_in_white_mode_drives_the_white_channel(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev, state=REAL_WHITE)
        p._set_brightness(dev, 50)
        self.assertIsNotNone(call_of(ctrl, "warm"))

    def test_a_failed_send_does_not_update_the_state(self):
        # Reporting success from the absence of an exception is how a plugin
        # logs a confident no-op.
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev, controller=FakeController(ok=False))
        p._set_brightness(dev, 60)
        self.assertEqual(dev.states["brightnessLevel"], 0)


class TestColourLevels(unittest.TestCase):

    def test_indigos_colour_picker_reaches_the_controller(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p._set_colour_levels(dev, {"redLevel": 100, "greenLevel": 0, "blueLevel": 50})
        self.assertEqual(call_of(ctrl, "colour")[:4], ("colour", 255, 0, 128))

    def test_a_missing_channel_keeps_its_current_value(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)                      # current state is full red
        p._set_colour_levels(dev, {"blueLevel": 100})
        self.assertEqual(call_of(ctrl, "colour")[:4], ("colour", 255, 0, 255))

    def test_asking_for_white_alone_uses_the_white_channel(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev, state=REAL_WHITE)
        p._set_colour_levels(dev, {"redLevel": 0, "greenLevel": 0, "blueLevel": 0,
                                   "whiteLevel": 100})
        self.assertEqual(call_of(ctrl, "warm"), ("warm", 255))


class TestActions(unittest.TestCase):

    def test_preset_action_sends_the_pattern(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p.action_preset(FakeAction(props={"pattern": "37", "speed": "80"}), dev)
        self.assertEqual(call_of(ctrl, "preset"), ("preset", 37, 80))

    def test_an_unknown_preset_is_refused_rather_than_sent(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p.action_preset(FakeAction(props={"pattern": "153"}), dev)
        self.assertIsNone(call_of(ctrl, "preset"))

    def test_cool_white_action_uses_the_cool_white_path(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p.action_cool_white(FakeAction(props={"level": "100"}), dev)
        self.assertEqual(call_of(ctrl, "cool"), ("cool", 255))

    def test_a_custom_pattern_with_no_usable_colours_is_refused(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p.action_custom_pattern(FakeAction(props={"palette": "nonsense"}), dev)
        self.assertIsNone(call_of(ctrl, "custom"))

    def test_a_custom_pattern_reaches_the_controller(self):
        p, dev = make_plugin(), FakeDevice()
        ctrl = wire(p, dev)
        p.action_custom_pattern(
            FakeAction(props={"palette": "255,0,0 / 0,0,255", "speed": "30",
                              "transition": "jump"}), dev)
        self.assertEqual(call_of(ctrl, "custom"), ("custom", ((255, 0, 0), (0, 0, 255)), 30, "jump"))

    def test_stopping_an_effect_that_is_not_running_says_so_quietly(self):
        p, dev = make_plugin(), FakeDevice()
        wire(p, dev)
        p.action_stop_effect(FakeAction(), dev)      # must not raise

    def test_an_action_on_an_unstarted_device_does_not_raise(self):
        p, dev = make_plugin(), FakeDevice(dev_id=99)
        p.action_warm_white(FakeAction(props={"level": "50"}), dev)


class TestDiscoveryCache(unittest.TestCase):
    """UDP broadcast is lossy, so a sweep can come back empty while every
    controller is sitting there perfectly happy."""

    def _plugin_with(self, sweeps):
        p = make_plugin()
        calls = {"n": 0}

        def fake_discover(timeout=4.0, **kwargs):
            result = sweeps[min(calls["n"], len(sweeps) - 1)]
            calls["n"] += 1
            return result

        plug.mdev.discover = fake_discover
        return p

    def setUp(self):
        self._real_discover = plug.mdev.discover

    def tearDown(self):
        plug.mdev.discover = self._real_discover

    def test_an_empty_sweep_does_not_erase_what_we_knew(self):
        # Overwriting the cache with an empty sweep turns one lost frame into
        # a houseful of devices with no address.
        entry = proto.Discovered(ip="192.168.1.9", mac="AABBCCDDEEFF",
                                 hardware_id="AK001", name="DDEEFF")
        p = self._plugin_with([[entry], []])
        p._refresh_discovery()
        self.assertEqual(len(p.store["discovered"]), 1)
        p._refresh_discovery()
        self.assertEqual(len(p.store["discovered"]), 1, "an empty sweep wiped the cache")

    def test_a_moved_controller_replaces_its_old_address(self):
        old = proto.Discovered(ip="192.168.1.9", mac="AABBCCDDEEFF",
                               hardware_id="AK001", name="DDEEFF")
        new = proto.Discovered(ip="192.168.1.44", mac="AABBCCDDEEFF",
                               hardware_id="AK001", name="DDEEFF")
        p = self._plugin_with([[old], [new]])
        p._refresh_discovery()
        p._refresh_discovery()
        self.assertEqual(p.store["discovered"]["AABBCCDDEEFF"].ip, "192.168.1.44")

    def test_a_failing_sweep_does_not_raise(self):
        def explode(**kwargs):
            raise OSError("network is down")
        plug.mdev.discover = explode
        p = make_plugin()
        self.assertEqual(p._refresh_discovery(), [])


class TestAddressRecovery(unittest.TestCase):
    """A controller that missed the sweep at startup must not stay dead."""

    def setUp(self):
        self._real_discover = plug.mdev.discover

    def tearDown(self):
        plug.mdev.discover = self._real_discover

    def test_a_device_with_no_address_is_looked_for_again(self):
        dev  = FakeDevice(props={"addressMode": "discover", "mac": "AABBCCDDEEFF"})
        p    = make_plugin()
        ctrl = wire(p, dev, controller=FakeController(ip=""))
        entry = proto.Discovered(ip="192.168.1.9", mac="AABBCCDDEEFF",
                                 hardware_id="AK001", name="DDEEFF")
        plug.mdev.discover = lambda **kw: [entry]

        self.assertTrue(p._try_to_find_address(dev, ctrl))
        self.assertEqual(ctrl.ip, "192.168.1.9")
        self.assertEqual(dev.states["controllerAddress"], "192.168.1.9")
        self.assertEqual(dev.errorState, "")

    def test_it_gives_up_quietly_when_the_controller_is_genuinely_absent(self):
        dev  = FakeDevice(props={"addressMode": "discover", "mac": "AABBCCDDEEFF"})
        p    = make_plugin()
        ctrl = wire(p, dev, controller=FakeController(ip=""))
        plug.mdev.discover = lambda **kw: []
        self.assertFalse(p._try_to_find_address(dev, ctrl))
        self.assertEqual(ctrl.ip, "")

    def test_a_fixed_ip_device_is_not_hunted_for(self):
        dev  = FakeDevice(props={"addressMode": "manual", "ipAddress": ""})
        p    = make_plugin()
        ctrl = wire(p, dev, controller=FakeController(ip=""))
        called = []
        plug.mdev.discover = lambda **kw: called.append(1) or []
        self.assertFalse(p._try_to_find_address(dev, ctrl))
        self.assertEqual(called, [])

    def test_sweeps_are_rate_limited_so_it_does_not_broadcast_every_poll(self):
        dev  = FakeDevice(props={"addressMode": "discover", "mac": "AABBCCDDEEFF"})
        p    = make_plugin()
        ctrl = wire(p, dev, controller=FakeController(ip=""))
        sweeps = []
        plug.mdev.discover = lambda **kw: sweeps.append(1) or []
        p.store["last_discovery"] = p._now()      # just swept
        p._try_to_find_address(dev, ctrl)
        self.assertEqual(sweeps, [], "swept again immediately")


class TestEffectPublishing(unittest.TestCase):

    def test_a_step_is_written_onto_the_device(self):
        import magichome_effects as fx
        p, dev = make_plugin(), FakeDevice()
        wire(p, dev)
        p._publish_step(dev, fx.Step(rgb=(255, 140, 60), white=None, hold=0))
        self.assertEqual(dev.states["redLevel"], 100)
        self.assertEqual(dev.states["greenLevel"], 55)
        self.assertEqual(dev.states["blueLevel"], 24)

    def test_a_white_step_is_written_onto_the_device(self):
        import magichome_effects as fx
        p, dev = make_plugin(), FakeDevice()
        wire(p, dev)
        p._publish_step(dev, fx.Step(rgb=None, white=255, hold=0))
        self.assertEqual(dev.states["whiteLevel"], 100)
        self.assertEqual(dev.states["brightnessLevel"], 100)


class TestDemo(unittest.TestCase):

    def test_the_plan_shows_each_colour_channel_separately(self):
        # Showing them one at a time is also how you spot a strip wired in the
        # wrong channel order.
        p = make_plugin()
        rgbs = [st.rgb for st in p._demo_plan(REAL_RED) if st.rgb is not None]
        for expected in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
            self.assertIn(expected, rgbs)

    def test_the_plan_shows_both_whites(self):
        # The difference between them is the most surprising thing about this
        # hardware, so a demo that skipped it would be missing the point.
        p    = make_plugin()
        plan = p._demo_plan(REAL_RED)
        self.assertTrue(any(st.white == 255 for st in plan), "no warm white")
        self.assertIn((255, 255, 255), [st.rgb for st in plan], "no cool white")

    def test_it_ends_where_it_started(self):
        p    = make_plugin()
        plan = p._demo_plan(REAL_RED)          # was full red, colour mode
        self.assertEqual(plan[-1].rgb, (255, 0, 0))

    def test_it_restores_a_light_that_was_in_white_mode(self):
        p    = make_plugin()
        plan = p._demo_plan(REAL_WHITE)
        self.assertIsNone(plan[-1].rgb)
        self.assertEqual(plan[-1].white, 255)

    def test_it_still_builds_when_the_previous_state_is_unknown(self):
        p = make_plugin()
        self.assertTrue(p._demo_plan(None))

    def test_it_is_short(self):
        p = make_plugin()
        length = sum(st.hold for st in p._demo_plan(REAL_RED))
        self.assertLess(length, 25, f"demo is {length:.0f}s, which is not short")
        self.assertGreater(length, 8)

    def test_it_refuses_a_light_with_no_address(self):
        p, dev = make_plugin(), FakeDevice()
        wire(p, dev, controller=FakeController(ip=""))
        self.assertFalse(p._start_demo(dev))

    def test_it_refuses_a_light_that_is_not_answering(self):
        # Nothing to demo, and starting anyway would log a confident no-op.
        p, dev = make_plugin(), FakeDevice()
        wire(p, dev, controller=FakeController(state=None))
        self.assertFalse(p._start_demo(dev))

    def test_the_button_refuses_when_nothing_is_picked(self):
        p = make_plugin()
        result = p.run_demo({"demoDevice": ""})
        self.assertEqual(result, {"demoDevice": ""})

    def test_the_button_returns_the_dialog_values_unchanged(self):
        p = make_plugin()
        values = {"demoDevice": "999999", "pollInterval": "15"}
        self.assertEqual(p.run_demo(values), values)

    def test_the_device_picker_lists_the_plugins_devices(self):
        # plugin.py holds its own reference to the indigo module, so the
        # devices have to be put on THAT one, not on a freshly installed stub.
        p = make_plugin()
        plug.indigo.devices.all = [FakeDevice(dev_id=42, name="Shelf Lights")]
        try:
            self.assertEqual(p.magic_home_devices(), [("42", "Shelf Lights")])
        finally:
            plug.indigo.devices.all = []

    def test_the_picker_says_so_when_there_are_no_devices(self):
        p = make_plugin()
        rows = p.magic_home_devices()
        self.assertEqual(len(rows), 1)
        self.assertIn("No MagicHome devices", rows[0][1])


class TestBannerExtras(unittest.TestCase):
    """The banner is what a user pastes into a bug report, so it failing is
    worse than most bugs — it takes out the thing they were reaching for."""

    def test_extras_are_label_value_pairs(self):
        # plugin_utils unpacks with `for label, value in extras`. A list of
        # pre-formatted strings makes it unpack a STRING into two names.
        p = make_plugin()
        for entry in p._banner_extras():
            self.assertIsInstance(entry, tuple)
            self.assertEqual(len(entry), 2)
            self.assertIsInstance(entry[0], str)
            self.assertIsInstance(entry[1], str)

    def test_the_real_plugin_utils_accepts_them(self):
        # Exercised against the SHIPPED utility, not a re-implementation —
        # the whole failure was a wrong assumption about its contract, and a
        # fake that shared the assumption would have passed happily.
        import plugin_utils
        lines = []
        original = plugin_utils.indigo
        try:
            plugin_utils.indigo = _CapturingIndigo(lines)
            p = make_plugin()
            plugin_utils.log_startup_banner("com.clives.indigoplugin.magichome",
                                            "MagicHome", "9.9.9",
                                            extras=p._banner_extras())
        finally:
            plugin_utils.indigo = original

        self.assertTrue(lines, "the banner produced nothing")
        self.assertTrue(lines[-1].startswith("="),
                        "no closing bar — the banner threw part way through")
        self.assertTrue(any("Poll interval:" in ln for ln in lines))

    def test_a_string_extras_list_would_still_be_caught(self):
        # Guards the guard: prove the check above can actually fail.
        import plugin_utils
        lines = []
        original = plugin_utils.indigo
        try:
            plugin_utils.indigo = _CapturingIndigo(lines)
            with self.assertRaises(ValueError):
                plugin_utils.log_startup_banner("x", "MagicHome", "9.9.9",
                                                extras=["Poll interval:  15s"])
        finally:
            plugin_utils.indigo = original


class _CapturingIndigo(object):
    """Just enough of the indigo module for plugin_utils to draw a banner."""

    def __init__(self, sink):
        self.server = type("S", (), {
            "log": staticmethod(lambda msg, **kw: sink.append(msg)),
            "version": "2025.2.0",
            "apiVersion": "3.8",
        })()


class TestPrefs(unittest.TestCase):

    def test_defaults_apply_when_nothing_is_saved(self):
        p = make_plugin({})
        self.assertEqual(p.poll_interval, plug.DEFAULT_POLL_INTERVAL)

    def test_string_prefs_are_converted(self):
        p = make_plugin({"pollInterval": "45", "effectFps": "10",
                         "rediscoverMinutes": "5"})
        self.assertEqual(p.poll_interval, 45)
        self.assertEqual(p.effect_fps, 10)
        self.assertEqual(p.rediscover_seconds, 300)

    def test_blank_prefs_do_not_take_the_plugin_down(self):
        p = make_plugin({"pollInterval": "", "effectFps": "", "rediscoverMinutes": ""})
        self.assertEqual(p.poll_interval, plug.DEFAULT_POLL_INTERVAL)

    def test_an_absurd_poll_interval_is_clamped_to_something_sane(self):
        p = make_plugin({"pollInterval": "1"})
        self.assertEqual(p.poll_interval, plug.MIN_POLL_INTERVAL)

    def test_validation_rejects_a_too_fast_poll(self):
        p = make_plugin()
        ok, _values, errors = p.validatePrefsConfigUi(
            {"pollInterval": "1", "effectFps": "20", "rediscoverMinutes": "15"})
        self.assertFalse(ok)
        self.assertIn("pollInterval", errors)

    def test_validation_accepts_sensible_values(self):
        p = make_plugin()
        result = p.validatePrefsConfigUi(
            {"pollInterval": "15", "effectFps": "20", "rediscoverMinutes": "15"})
        self.assertTrue(result[0])


class TestDeviceConfigValidation(unittest.TestCase):

    def test_discovery_mode_needs_a_controller_chosen(self):
        p = make_plugin()
        ok, _v, errors = p.validateDeviceConfigUi(
            {"addressMode": "discover", "mac": "", "pollInterval": "15"},
            "magicHomeLight", 1)
        self.assertFalse(ok)
        self.assertIn("mac", errors)

    def test_manual_mode_needs_an_address(self):
        p = make_plugin()
        ok, _v, errors = p.validateDeviceConfigUi(
            {"addressMode": "manual", "ipAddress": "", "pollInterval": "15"},
            "magicHomeLight", 1)
        self.assertFalse(ok)
        self.assertIn("ipAddress", errors)

    def test_a_hostname_in_the_ip_field_is_caught(self):
        p = make_plugin()
        ok, _v, errors = p.validateDeviceConfigUi(
            {"addressMode": "manual", "ipAddress": "lights", "pollInterval": "15"},
            "magicHomeLight", 1)
        self.assertFalse(ok)

    def test_a_complete_config_passes(self):
        p = make_plugin()
        result = p.validateDeviceConfigUi(
            {"addressMode": "discover", "mac": "806A34112233", "pollInterval": "15"},
            "magicHomeLight", 1)
        self.assertTrue(result[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
