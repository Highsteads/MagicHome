#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    magichome_effects.py
# Description: Plugin-driven lighting effects — smooth fades, colour drift and
#              sunrise, computed here rather than left to the controller
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.0
#
# The controller's own presets are strobes and hard jumps, which suit a party
# and not a shelf. These effects are computed by the plugin and streamed as
# ordinary colour commands, so they can be as slow and as smooth as wanted.
#
# The plan is separated from the running of it. Every plan_* function is pure —
# no clock, no socket, no thread — so the maths is testable on its own, and the
# runner is a small loop with nothing to get wrong.

import logging
import threading
import time
from collections import namedtuple

LOG = logging.getLogger("Plugin.magichome")

DEFAULT_FPS   = 20      # updates per second; the controller drops much above this
MAX_FPS       = 25
MIN_FPS       = 1
MAX_STEPS     = 60000   # a plan longer than this is a runaway, not an effect

# One instruction: show this, then wait. `rgb` or `white` may be None, meaning
# "leave that half of the fixture alone".
Step = namedtuple("Step", "rgb white hold")


# ---------------------------------------------------------------------------
# Easing
# ---------------------------------------------------------------------------

def _linear(t):
    return t


def _smooth(t):
    """Smoothstep. Starts and ends gently, which is what reads as natural."""
    return t * t * (3.0 - 2.0 * t)


def _gamma(t):
    """Perceptual ramp for brightness.

    An LED driven on a straight line looks like it rushes the dark end and
    crawls the bright end, because the eye is nothing like linear. This is what
    makes a sunrise look like a sunrise instead of a dimmer being wound up.
    """
    return t ** 2.2


EASINGS = {"linear": _linear, "smooth": _smooth, "gamma": _gamma}


def _clamp_fps(fps):
    try:
        fps = float(fps)
    except (TypeError, ValueError):
        return DEFAULT_FPS
    return max(MIN_FPS, min(MAX_FPS, fps))


def _clamp_byte(value):
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(255, value))


def _blend(start, end, t):
    return tuple(_clamp_byte(a + (b - a) * t) for a, b in zip(start, end))


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

def plan_fade(start_rgb, end_rgb, duration, fps=DEFAULT_FPS, ease="smooth",
              start_white=None, end_white=None):
    """Fade from one colour to another over `duration` seconds.

    The final step is always the exact target. Landing a hair off because of
    rounding leaves the lights on a colour nobody asked for, and the state poll
    then reports that as the truth.
    """
    fps      = _clamp_fps(fps)
    easing   = EASINGS.get(str(ease).lower(), _smooth)
    try:
        duration = max(0.0, float(duration))
    except (TypeError, ValueError):
        duration = 0.0

    steps_wanted = int(round(duration * fps))
    steps_wanted = max(1, min(steps_wanted, MAX_STEPS))
    hold         = duration / steps_wanted if steps_wanted else 0.0

    fading_white = start_white is not None and end_white is not None
    plan = []
    for index in range(1, steps_wanted + 1):
        t   = easing(index / float(steps_wanted))
        rgb = _blend(start_rgb, end_rgb, t) if start_rgb and end_rgb else None
        white = (_clamp_byte(start_white + (end_white - start_white) * t)
                 if fading_white else None)
        plan.append(Step(rgb=rgb, white=white, hold=hold))

    # Snap the last step onto the target exactly.
    if plan:
        last = plan[-1]
        plan[-1] = Step(
            rgb=tuple(_clamp_byte(v) for v in end_rgb) if last.rgb is not None else None,
            white=_clamp_byte(end_white) if last.white is not None else None,
            hold=last.hold)
    return plan


def plan_drift(palette, hold=30.0, fade=8.0, fps=DEFAULT_FPS, cycles=None,
               ease="smooth"):
    """Wander slowly around a palette, crossfading between colours.

    Returns a generator, because the usual case is "keep going until told to
    stop" and building that as a list would be a list without an end.
    """
    colours = [tuple(_clamp_byte(c) for c in rgb) for rgb in (palette or [])]
    if not colours:
        raise ValueError("a drift needs at least one colour")
    if len(colours) == 1:
        colours = colours * 2

    try:
        hold = max(0.0, float(hold))
    except (TypeError, ValueError):
        hold = 30.0

    def generate():
        index = 0
        loops = 0
        while cycles is None or loops < cycles:
            current = colours[index % len(colours)]
            nxt     = colours[(index + 1) % len(colours)]
            if hold > 0:
                yield Step(rgb=current, white=None, hold=hold)
            for step in plan_fade(current, nxt, fade, fps=fps, ease=ease):
                yield step
            index += 1
            if index % len(colours) == 0:
                loops += 1

    return generate()


def plan_sunrise(duration, fps=DEFAULT_FPS, ember=(60, 6, 0), peak=(255, 170, 90),
                 peak_white=None):
    """Ember to daylight over `duration` seconds, on a perceptual ramp.

    Split in two: the first two-thirds climbs out of the ember reds, the last
    third opens up into the warm white. Done as one straight fade it looks like
    somebody turning a knob.
    """
    try:
        duration = max(1.0, float(duration))
    except (TypeError, ValueError):
        duration = 600.0

    mid = tuple(_clamp_byte(e + (p - e) * 0.55) for e, p in zip(ember, peak))
    plan = plan_fade(ember, mid, duration * 0.66, fps=fps, ease="gamma")

    plan += plan_fade(mid, peak, duration * 0.34, fps=fps, ease="smooth")

    if peak_white is not None:
        # An RGBW fixture shows colour OR white, so the two cannot be
        # crossfaded — measured, not assumed. Finish with a clean switch to the
        # white channel at full rather than a fade that would only ever apply
        # half of itself.
        plan.append(Step(rgb=None, white=_clamp_byte(peak_white), hold=0.0))
    return plan


def plan_flash(rgb, times=3, on=0.4, off=0.4, restore_rgb=None):
    """A short attention-getter — a doorbell or an alert, not a party strobe."""
    times = max(1, min(int(times or 1), 20))
    plan  = []
    dark  = (0, 0, 0)
    for _ in range(times):
        plan.append(Step(rgb=tuple(_clamp_byte(c) for c in rgb), white=None, hold=on))
        plan.append(Step(rgb=dark, white=None, hold=off))
    if restore_rgb is not None:
        plan.append(Step(rgb=tuple(_clamp_byte(c) for c in restore_rgb),
                         white=None, hold=0.0))
    return plan


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class EffectRunner(object):
    """Walks a plan on its own thread, one controller at a time.

    Only ever one effect per controller. Starting a second stops the first
    rather than letting two threads fight over the same lights, which would
    read as flicker and be very hard to explain afterwards.
    """

    def __init__(self, controller, allow_simultaneous=False, logger=None):
        self.controller         = controller
        self.allow_simultaneous = allow_simultaneous
        self.logger             = logger or LOG
        self.name               = ""
        self._thread            = None
        self._stop              = threading.Event()
        self._lock              = threading.RLock()
        self.last_step          = None
        self.completed          = False

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, name, steps, on_finish=None):
        with self._lock:
            self.stop()
            self._stop = threading.Event()
            self.name       = name
            self.completed  = False
            self._thread = threading.Thread(
                target=self._run, args=(steps, self._stop, on_finish),
                name=f"MagicHome-{name}", daemon=True)
            self._thread.start()
        return True

    def stop(self, wait=True, timeout=3.0):
        thread = self._thread
        self._stop.set()
        if wait and thread is not None and thread.is_alive():
            thread.join(timeout)
            if thread.is_alive():
                # Say so rather than carrying on as though it stopped.
                self.logger.warning("Effect %r did not stop within %ss", self.name, timeout)
        self._thread = None
        return True

    def _apply(self, step):
        ctrl = self.controller
        if step.rgb is not None and step.white is not None and self.allow_simultaneous:
            return ctrl.set_colour(step.rgb[0], step.rgb[1], step.rgb[2], white=step.white)
        # Where both channels cannot be driven at once, sending both in turn
        # would leave only the second one showing. Apply the one that was
        # evidently meant instead.
        if step.rgb is not None and any(step.rgb):
            return ctrl.set_colour(step.rgb[0], step.rgb[1], step.rgb[2])
        if step.white is not None:
            return ctrl.set_warm_white(step.white)
        if step.rgb is not None:
            return ctrl.set_colour(step.rgb[0], step.rgb[1], step.rgb[2])
        return True

    def _run(self, steps, stop_event, on_finish):
        failures = 0
        try:
            for step in steps:
                if stop_event.is_set():
                    return
                if not self._apply(step):
                    failures += 1
                    # A controller that has gone away will not come back inside
                    # one effect. Give up rather than hammering it for an hour.
                    if failures >= 5:
                        self.logger.warning(
                            "Effect %r stopped — %s stopped answering",
                            self.name, getattr(self.controller, "name", "controller"))
                        return
                else:
                    failures = 0
                self.last_step = step
                if step.hold > 0 and stop_event.wait(step.hold):
                    return
            self.completed = True
        except Exception:
            # One bad effect must never take the plugin's worker down with it.
            self.logger.exception("Effect %r failed", self.name)
        finally:
            if on_finish is not None and not stop_event.is_set():
                try:
                    on_finish(self.completed)
                except Exception:
                    self.logger.exception("Effect %r finish callback failed", self.name)
