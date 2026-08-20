#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_effects.py
# Description: Contract tests for the plugin-driven effects engine
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.0

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "MagicHome.indigoPlugin", "Contents", "Server Plugin"))

import magichome_effects as fx      # noqa: E402


class FakeController(object):
    """Records what an effect asked for, and can start refusing."""

    name = "fake"

    def __init__(self, fail_after=None):
        self.colours    = []
        self.whites     = []
        self.fail_after = fail_after
        self.calls      = 0

    def _ok(self):
        self.calls += 1
        return not (self.fail_after is not None and self.calls > self.fail_after)

    def set_colour(self, red, green, blue, white=None):
        ok = self._ok()
        if ok:
            self.colours.append((red, green, blue, white))
        return ok

    def set_warm_white(self, level):
        ok = self._ok()
        if ok:
            self.whites.append(level)
        return ok


class TestFadePlans(unittest.TestCase):

    def test_step_count_follows_duration_and_rate(self):
        self.assertEqual(len(fx.plan_fade((0, 0, 0), (255, 255, 255), 2, fps=10)), 20)

    def test_it_lands_exactly_on_the_target(self):
        # Landing a hair off leaves the lights on a colour nobody asked for,
        # and the next state poll then reports that as the truth.
        plan = fx.plan_fade((0, 0, 0), (137, 42, 9), 3, fps=7)
        self.assertEqual(plan[-1].rgb, (137, 42, 9))

    def test_the_holds_add_up_to_the_duration(self):
        plan = fx.plan_fade((0, 0, 0), (255, 0, 0), 5, fps=10)
        self.assertAlmostEqual(sum(s.hold for s in plan), 5.0, places=3)

    def test_it_moves_in_one_direction_only(self):
        plan = fx.plan_fade((0, 0, 0), (255, 0, 0), 4, fps=10)
        reds = [s.rgb[0] for s in plan]
        self.assertEqual(reds, sorted(reds))

    def test_a_zero_duration_still_reaches_the_target(self):
        plan = fx.plan_fade((0, 0, 0), (10, 20, 30), 0)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].rgb, (10, 20, 30))

    def test_a_runaway_duration_is_capped(self):
        self.assertLessEqual(len(fx.plan_fade((0, 0, 0), (1, 1, 1), 10 ** 7)), fx.MAX_STEPS)

    def test_rubbish_duration_does_not_raise(self):
        self.assertTrue(fx.plan_fade((0, 0, 0), (1, 1, 1), None))
        self.assertTrue(fx.plan_fade((0, 0, 0), (1, 1, 1), "soon"))

    def test_the_frame_rate_is_clamped_to_what_the_controller_takes(self):
        plan = fx.plan_fade((0, 0, 0), (255, 0, 0), 1, fps=5000)
        self.assertLessEqual(len(plan), fx.MAX_FPS)

    def test_white_is_left_alone_unless_both_ends_are_given(self):
        self.assertIsNone(fx.plan_fade((0, 0, 0), (1, 1, 1), 1)[-1].white)
        self.assertIsNone(fx.plan_fade((0, 0, 0), (1, 1, 1), 1, start_white=0)[-1].white)

    def test_white_fades_when_both_ends_are_given(self):
        plan = fx.plan_fade((0, 0, 0), (1, 1, 1), 1, start_white=0, end_white=200)
        self.assertEqual(plan[-1].white, 200)

    def test_smooth_easing_starts_gentler_than_linear(self):
        smooth = fx.plan_fade((0, 0, 0), (255, 0, 0), 4, fps=10, ease="smooth")
        linear = fx.plan_fade((0, 0, 0), (255, 0, 0), 4, fps=10, ease="linear")
        self.assertLess(smooth[1].rgb[0], linear[1].rgb[0])

    def test_an_unknown_easing_falls_back_rather_than_raising(self):
        self.assertTrue(fx.plan_fade((0, 0, 0), (1, 1, 1), 1, ease="bounce"))


class TestDriftPlans(unittest.TestCase):

    def test_it_cycles_the_palette_and_returns_home(self):
        steps = list(fx.plan_drift([(255, 0, 0), (0, 0, 255)], hold=1, fade=1,
                                   fps=4, cycles=1))
        self.assertEqual(steps[0].rgb, (255, 0, 0))
        self.assertEqual(steps[-1].rgb, (255, 0, 0))

    def test_a_hold_step_comes_before_each_fade(self):
        steps = list(fx.plan_drift([(255, 0, 0), (0, 255, 0)], hold=30, fade=1,
                                   fps=4, cycles=1))
        self.assertEqual(steps[0].hold, 30)

    def test_no_cycle_limit_yields_indefinitely(self):
        gen = fx.plan_drift([(1, 2, 3), (4, 5, 6)], hold=0, fade=1, fps=2)
        self.assertEqual(len([next(gen) for _ in range(200)]), 200)

    def test_a_single_colour_palette_is_allowed(self):
        self.assertTrue(list(fx.plan_drift([(9, 9, 9)], hold=0, fade=1, fps=2, cycles=1)))

    def test_an_empty_palette_is_refused_loudly(self):
        with self.assertRaises(ValueError):
            fx.plan_drift([])


class TestSunrisePlan(unittest.TestCase):

    def test_it_starts_in_the_embers_and_ends_at_the_peak(self):
        plan = fx.plan_sunrise(60, fps=5)
        self.assertLess(plan[0].rgb[0], 80)
        self.assertEqual(plan[-1].rgb, (255, 170, 90))

    def test_it_climbs_slowly_at_first(self):
        # A straight line looks like a dimmer being wound up, because the eye
        # is nothing like linear.
        plan = fx.plan_sunrise(100, fps=5)
        first_tenth = plan[len(plan) // 10].rgb[0] - plan[0].rgb[0]
        last_tenth  = plan[-1].rgb[0] - plan[-len(plan) // 10].rgb[0]
        self.assertLess(first_tenth, last_tenth)

    def test_it_can_finish_on_the_white_channel(self):
        plan = fx.plan_sunrise(60, fps=5, peak_white=255)
        self.assertEqual(plan[-1].white, 255)

    def test_rubbish_duration_does_not_raise(self):
        self.assertTrue(fx.plan_sunrise(None))


class TestFlashPlan(unittest.TestCase):

    def test_it_flashes_the_requested_number_of_times(self):
        self.assertEqual(len(fx.plan_flash((255, 0, 0), times=3)), 6)

    def test_it_restores_the_previous_colour_when_asked(self):
        plan = fx.plan_flash((255, 0, 0), times=2, restore_rgb=(1, 2, 3))
        self.assertEqual(plan[-1].rgb, (1, 2, 3))

    def test_an_absurd_count_is_capped(self):
        self.assertLessEqual(len(fx.plan_flash((1, 1, 1), times=9999)), 40)


class TestRunner(unittest.TestCase):

    def test_it_walks_the_whole_plan(self):
        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl)
        runner.start("fade", fx.plan_fade((0, 0, 0), (255, 0, 0), 0.1, fps=10))
        runner._thread.join(3)
        self.assertEqual(ctrl.colours[-1][:3], (255, 0, 0))
        self.assertTrue(runner.completed)

    def test_stop_halts_it_part_way(self):
        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl)
        runner.start("drift", fx.plan_drift([(1, 0, 0), (0, 0, 1)], hold=0.05,
                                            fade=5, fps=20))
        time.sleep(0.2)
        runner.stop()
        self.assertFalse(runner.running)
        settled = len(ctrl.colours)
        time.sleep(0.15)
        self.assertEqual(len(ctrl.colours), settled)

    def test_starting_a_second_effect_stops_the_first(self):
        # Two threads fighting over one set of lights reads as flicker and is
        # very hard to explain afterwards.
        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl)
        runner.start("one", fx.plan_drift([(1, 0, 0)], hold=0.02, fade=9, fps=20))
        first = runner._thread
        runner.start("two", fx.plan_fade((0, 0, 0), (9, 9, 9), 0.05, fps=10))
        self.assertFalse(first.is_alive())
        self.assertEqual(runner.name, "two")

    def test_only_one_thread_survives_a_burst_of_starts(self):
        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl)
        for _ in range(6):
            runner.start("x", fx.plan_drift([(1, 0, 0)], hold=0.02, fade=9, fps=20))
        live = [t for t in threading.enumerate() if t.name.startswith("MagicHome-")]
        runner.stop()
        self.assertLessEqual(len(live), 1)

    def test_it_gives_up_on_a_controller_that_stopped_answering(self):
        ctrl   = FakeController(fail_after=3)
        runner = fx.EffectRunner(ctrl)
        runner.start("fade", fx.plan_fade((0, 0, 0), (255, 0, 0), 30, fps=20))
        runner._thread.join(5)
        self.assertFalse(runner.running)
        self.assertFalse(runner.completed)

    def test_a_broken_plan_does_not_escape_the_thread(self):
        def exploding():
            yield fx.Step(rgb=(1, 2, 3), white=None, hold=0)
            raise RuntimeError("bad plan")

        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl, logger=_QuietLogger())
        runner.start("boom", exploding())
        runner._thread.join(3)
        self.assertFalse(runner.running)

    def test_the_finish_callback_fires_on_completion(self):
        seen   = []
        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl)
        runner.start("fade", fx.plan_fade((0, 0, 0), (1, 1, 1), 0.05, fps=10),
                     on_finish=seen.append)
        runner._thread.join(3)
        self.assertEqual(seen, [True])

    def test_the_finish_callback_does_not_fire_when_stopped(self):
        seen   = []
        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl)
        runner.start("drift", fx.plan_drift([(1, 0, 0)], hold=0.02, fade=9, fps=20),
                     on_finish=seen.append)
        time.sleep(0.1)
        runner.stop()
        time.sleep(0.1)
        self.assertEqual(seen, [])

    def test_white_and_colour_go_separately_unless_the_model_allows_both(self):
        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl, allow_simultaneous=False)
        runner.start("mix", [fx.Step(rgb=(1, 2, 3), white=44, hold=0)])
        runner._thread.join(3)
        self.assertEqual(ctrl.colours[-1], (1, 2, 3, None))
        self.assertEqual(ctrl.whites[-1], 44)

    def test_both_go_in_one_message_when_the_model_allows_it(self):
        ctrl   = FakeController()
        runner = fx.EffectRunner(ctrl, allow_simultaneous=True)
        runner.start("mix", [fx.Step(rgb=(1, 2, 3), white=44, hold=0)])
        runner._thread.join(3)
        self.assertEqual(ctrl.colours[-1], (1, 2, 3, 44))
        self.assertEqual(ctrl.whites, [])


class _QuietLogger(object):
    def warning(self, *a, **k):
        pass

    def exception(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
