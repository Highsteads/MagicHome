#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: MagicHome — direct local control of Zengge / Magic Home WiFi
#              LED controllers, with no cloud account and no app
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.1.3

import os as _os
import sys as _sys

import indigo

_sys.path.insert(0, _os.getcwd())

import magichome_device as mdev
import magichome_effects as fx
import magichome_protocol as proto

try:
    from plugin_utils import log_startup_banner, as_bool, install_timestamp_filter
except ImportError:                                     # pragma: no cover
    log_startup_banner = None
    install_timestamp_filter = None

    def as_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        text = str(value).strip().lower()
        if text in ("true", "yes", "on", "1"):
            return True
        if text in ("false", "no", "off", "0"):
            return False
        return default

PLUGIN_VERSION = "1.1.3"

DEFAULT_POLL_INTERVAL = 15
MIN_POLL_INTERVAL     = 5
DEFAULT_REDISCOVER    = 15          # minutes
LOOP_TICK             = 1.0         # seconds
EFFECT_PUBLISH_GAP    = 1.0         # seconds between state writes during an effect
ADDRESS_RETRY_GAP     = 60          # seconds between sweeps hunting a missing controller


# ---------------------------------------------------------------------------
# Coercion helpers
#
# Indigo re-serialises every ConfigUI field as a STRING once a dialog has been
# saved, including menu options that look like numbers. So nothing arriving
# from a dialog may be used as a number without being converted first, and
# every conversion needs a guard: a field left blank makes int("") raise, and
# an unguarded one in startup or deviceStartComm takes the plugin down with it.
# ---------------------------------------------------------------------------

def as_int(value, default=0, low=None, high=None):
    try:
        result = int(round(float(value)))
    except (TypeError, ValueError):
        result = default
    if low is not None:
        result = max(low, result)
    if high is not None:
        result = min(high, result)
    return result


def as_float(value, default=0.0, low=None, high=None):
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    if low is not None:
        result = max(low, result)
    if high is not None:
        result = min(high, result)
    return result


def parse_palette(text):
    """Turn '255,0,0 / 0,255,0' into [(255,0,0), (0,255,0)].

    Anything unparseable is skipped rather than silently turned into black —
    a stray blank would otherwise show as a blackout in the middle of a fade.
    """
    colours = []
    for chunk in str(text or "").replace(";", "/").split("/"):
        parts = [p for p in chunk.replace(",", " ").split() if p]
        if len(parts) != 3:
            continue
        try:
            rgb = tuple(max(0, min(255, int(round(float(p))))) for p in parts)
        except (TypeError, ValueError):
            continue
        colours.append(rgb)
    return colours


def describe_span(seconds):
    """Say a duration in a unit that carries meaning.

    A twelve second sunrise logged as "0 minute" is a number that means
    nothing, and a number that means nothing reads as a measurement.
    """
    seconds = as_float(seconds, 0.0, 0.0)
    if seconds < 90:
        return f"{seconds:.0f} second"
    if seconds < 5400:
        return f"{seconds / 60.0:.0f} minute"
    return f"{seconds / 3600.0:.1f} hour"


def to_percent(byte_value):
    return int(round(as_int(byte_value, 0, 0, 255) / 255.0 * 100.0))


def to_byte(percent):
    return int(round(as_float(percent, 0.0, 0.0, 100.0) / 100.0 * 255.0))


class Plugin(indigo.PluginBase):

    # -- lifecycle ----------------------------------------------------------

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        # One mutable store rather than module globals: globals do not survive
        # reliably across plugin callbacks.
        self.store = {
            "controllers":    {},      # dev.id -> Controller
            "effects":        {},      # dev.id -> EffectRunner
            "hue":            {},      # dev.id -> (r, g, b) at full brightness
            "discovered":     {},      # normalised MAC -> Discovered
            "last_discovery": 0.0,
            "next_poll":      {},      # dev.id -> epoch seconds
        }

        self.poll_interval      = DEFAULT_POLL_INTERVAL
        self.rediscover_seconds = DEFAULT_REDISCOVER * 60
        self.effect_fps         = fx.DEFAULT_FPS
        self.discover_on_start  = True

        self._read_prefs(pluginPrefs)

        if install_timestamp_filter:
            install_timestamp_filter(self, True)

    def _read_prefs(self, prefs):
        prefs = prefs or {}
        self.poll_interval      = as_int(prefs.get("pollInterval", DEFAULT_POLL_INTERVAL),
                                         DEFAULT_POLL_INTERVAL, MIN_POLL_INTERVAL, 3600)
        self.rediscover_seconds = as_int(prefs.get("rediscoverMinutes", DEFAULT_REDISCOVER),
                                         DEFAULT_REDISCOVER, 1, 1440) * 60
        self.effect_fps         = as_int(prefs.get("effectFps", fx.DEFAULT_FPS),
                                         fx.DEFAULT_FPS, fx.MIN_FPS, fx.MAX_FPS)
        self.discover_on_start  = as_bool(prefs.get("discoverOnStartup", True), True)
        self.debug              = as_bool(prefs.get("debugLogging", False), False)
        self.logLevel           = 10 if self.debug else 20
        self.indigo_log_handler.setLevel(self.logLevel)

    def startup(self):
        # Indigo already logs "Starting plugin ...". One line of genuine state
        # is enough on top of that.
        if self.discover_on_start:
            found = self._refresh_discovery()
            self.logger.info(f"MagicHome ready — {len(found)} controller(s) found on the network")
        else:
            self.logger.info("MagicHome ready — network discovery is switched off")

    def shutdown(self):
        for runner in list(self.store["effects"].values()):
            try:
                runner.stop(wait=True, timeout=2.0)
            except Exception:
                self.logger.exception("Failed to stop an effect during shutdown")
        for controller in list(self.store["controllers"].values()):
            try:
                controller.close()
            except Exception:
                pass

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if userCancelled:
            return
        # Mirror the startup guards. A dialog save that skipped them would
        # leave the plugin running on values startup would have rejected.
        self._read_prefs(valuesDict)
        self.logger.info(
            f"Settings saved — polling every {self.poll_interval}s, "
            f"effects at {self.effect_fps} updates/second")

    def validatePrefsConfigUi(self, valuesDict):
        errors = indigo.Dict()
        if as_int(valuesDict.get("pollInterval"), 0) < MIN_POLL_INTERVAL:
            errors["pollInterval"] = f"Use {MIN_POLL_INTERVAL} seconds or more."
        if not (fx.MIN_FPS <= as_int(valuesDict.get("effectFps"), 0) <= fx.MAX_FPS):
            errors["effectFps"] = f"Use a number between {fx.MIN_FPS} and {fx.MAX_FPS}."
        if as_int(valuesDict.get("rediscoverMinutes"), 0) < 1:
            errors["rediscoverMinutes"] = "Use 1 minute or more."
        if errors:
            return (False, valuesDict, errors)
        return (True, valuesDict)

    # -- devices ------------------------------------------------------------

    def deviceStartComm(self, dev):
        props = dev.pluginProps
        ip    = self._address_for(dev, props)

        controller = mdev.Controller(
            ip=ip or "",
            mac=props.get("mac", ""),
            name=dev.name,
            timeout=4.0,
        )
        self.store["controllers"][dev.id] = controller
        self.store["effects"][dev.id]     = fx.EffectRunner(
            controller,
            allow_simultaneous=as_bool(props.get("SupportsRGBandWhiteSimultaneously"), False),
            logger=self.logger)
        self.store["next_poll"][dev.id]   = 0.0

        if not ip:
            # Awaiting configuration is not a fault, so it is not logged as one.
            self.logger.info(f"\"{dev.name}\" has no address yet — run "
                             f"Plugins -> MagicHome -> Discover Controllers, then edit the device")
            dev.updateStateOnServer("online", False)
            dev.setErrorStateOnServer("no address")
            return

        dev.updateStateOnServer("controllerAddress", ip)
        self._poll_device(dev, force=True)
        self._assert_capabilities(dev, controller)

    def _assert_capabilities(self, dev, controller):
        """Tell Indigo what this controller can do, from what it reports.

        The Supports* properties are how Indigo decides which controls to offer
        and which actions to dispatch, and the documented way to set them is
        replacePluginPropsOnServer — which makes the server rebuild the
        device's capabilities. Leaving them to whatever the device happened to
        be created with means trusting a guess made before the hardware had
        said a word.

        replacePluginPropsOnServer REPLACES rather than merges, so the whole
        dict goes back, and it is only called when something actually differs
        — writing identical props on every start would churn the device for no
        reason.
        """
        model = proto.model_for(controller.model_num or 0x06)
        wanted = {
            "SupportsColor":                     True,
            "SupportsRGB":                       "RGB" in model.channels,
            "SupportsWhite":                     bool(model.has_white),
            "SupportsTwoWhiteLevels":            bool(model.has_two_whites),
            "SupportsWhiteTemperature":          False,
            "SupportsRGBandWhiteSimultaneously": bool(model.honours_both),
        }

        props   = dict(dev.pluginProps)
        changed = {k: v for k, v in wanted.items() if props.get(k) != v}
        if not changed:
            return False

        props.update(wanted)
        dev.replacePluginPropsOnServer(props)
        self.logger.info(f"\"{dev.name}\" is a {model.name} ({model.channels}) — "
                         f"told Indigo its capabilities: "
                         + ", ".join(f"{k.replace('Supports', '')}={v}"
                                     for k, v in sorted(changed.items())))
        return True

    def deviceStopComm(self, dev):
        runner = self.store["effects"].pop(dev.id, None)
        if runner is not None:
            runner.stop(wait=True, timeout=2.0)
        controller = self.store["controllers"].pop(dev.id, None)
        if controller is not None:
            controller.close()
        self.store["hue"].pop(dev.id, None)
        self.store["next_poll"].pop(dev.id, None)

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        errors = indigo.Dict()
        mode = valuesDict.get("addressMode", "discover")
        if mode == "manual":
            ip = str(valuesDict.get("ipAddress", "")).strip()
            if not ip:
                errors["ipAddress"] = "Enter the controller's IP address."
            elif len(ip.split(".")) != 4:
                errors["ipAddress"] = "That does not look like an IP address."
        else:
            if not str(valuesDict.get("mac", "")).strip():
                errors["mac"] = ("Pick a controller. If the list is empty, run "
                                 "Plugins -> MagicHome -> Discover Controllers first.")
        if as_int(valuesDict.get("pollInterval"), 0) < MIN_POLL_INTERVAL:
            errors["pollInterval"] = f"Use {MIN_POLL_INTERVAL} seconds or more."
        if errors:
            return (False, valuesDict, errors)
        return (True, valuesDict)

    def _address_for(self, dev, props=None):
        """Work out where this controller is right now."""
        props = props if props is not None else dev.pluginProps
        if props.get("addressMode", "discover") == "manual":
            return str(props.get("ipAddress", "")).strip()

        mac = proto.normalise_mac(props.get("mac", ""))
        if not mac:
            return ""
        entry = self.store["discovered"].get(mac)
        if entry is not None:
            return entry.ip
        # Not in the cache — go and look, because the alternative is a device
        # that stays dead until somebody happens to run discovery by hand.
        self._refresh_discovery()
        entry = self.store["discovered"].get(mac)
        return entry.ip if entry is not None else ""

    # -- discovery ----------------------------------------------------------

    def _refresh_discovery(self, timeout=4.0):
        """Sweep for controllers and MERGE the result into what we know.

        Deliberately a merge and not a replacement. UDP broadcast is lossy, so
        a sweep can come back empty while every controller is sitting there
        perfectly happy — and overwriting the cache with that would turn one
        lost frame into a houseful of devices with no address. An empty sweep
        means "nothing answered this time", never "there is nothing there".
        """
        try:
            found = mdev.discover(timeout=timeout)
        except Exception:
            self.logger.exception("Controller discovery failed")
            return []
        for entry in found:
            self.store["discovered"][proto.normalise_mac(entry.mac)] = entry
        self.store["last_discovery"] = self._now()
        return found

    @staticmethod
    def _now():
        import time
        return time.time()

    def discovered_controllers(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Dynamic list for the device dialog."""
        entries = self.store["discovered"]
        if not entries:
            self._refresh_discovery()
            entries = self.store["discovered"]
        rows = [(mac, f"{entry.name} — {entry.ip}") for mac, entry in sorted(entries.items())]
        if not rows:
            rows = [("", "No controllers found — run Discover Controllers")]
        return rows

    def preset_list(self, filter="", valuesDict=None, typeId="", targetId=0):
        return [(str(code), name) for code, name in sorted(proto.PRESETS.items())]

    # -- worker -------------------------------------------------------------

    def runConcurrentThread(self):
        import time
        last_rediscovery = self._now()
        try:
            while True:
                # The whole tick is wrapped. One controller throwing must not
                # take the worker down and silently end all polling.
                try:
                    now = self._now()

                    if now - last_rediscovery >= self.rediscover_seconds:
                        last_rediscovery = now
                        self._rediscover_and_repoint()

                    for dev in indigo.devices.iter("self.magicHomeLight"):
                        if not dev.enabled or not dev.configured:
                            continue
                        try:
                            if now >= self.store["next_poll"].get(dev.id, 0.0):
                                self._poll_device(dev)
                        except Exception:
                            self.logger.exception(f"Polling \"{dev.name}\" failed")
                            self.store["next_poll"][dev.id] = now + self.poll_interval
                except Exception:
                    self.logger.exception("MagicHome worker tick failed")

                self.sleep(LOOP_TICK)
        except self.StopThread:
            pass

    def _try_to_find_address(self, dev, controller):
        """Look again for a controller we have never managed to place."""
        props = dev.pluginProps
        if props.get("addressMode", "discover") != "discover":
            return False
        mac = proto.normalise_mac(props.get("mac", ""))
        if not mac:
            return False

        entry = self.store["discovered"].get(mac)
        if entry is None:
            if self._now() - self.store["last_discovery"] < ADDRESS_RETRY_GAP:
                return False
            self._refresh_discovery()
            entry = self.store["discovered"].get(mac)
        if entry is None or not entry.ip:
            return False

        controller.ip = entry.ip
        controller.failures = 0
        controller._retry_after = 0.0
        self.logger.info(f"\"{dev.name}\" found at {entry.ip}")
        dev.updateStateOnServer("controllerAddress", entry.ip)
        dev.setErrorStateOnServer("")
        return True

    def _rediscover_and_repoint(self):
        """Catch a controller that DHCP has moved."""
        before = {mac: entry.ip for mac, entry in self.store["discovered"].items()}
        self._refresh_discovery()
        for dev in indigo.devices.iter("self.magicHomeLight"):
            if not dev.enabled:
                continue
            props = dev.pluginProps
            if props.get("addressMode", "discover") != "discover":
                continue
            mac = proto.normalise_mac(props.get("mac", ""))
            entry = self.store["discovered"].get(mac)
            controller = self.store["controllers"].get(dev.id)
            if entry is None or controller is None:
                continue
            if entry.ip and entry.ip != controller.ip:
                self.logger.info(f"\"{dev.name}\" has moved from {controller.ip or 'nowhere'} "
                                 f"to {entry.ip}")
                controller.close()
                controller.ip = entry.ip
                controller.failures = 0
                controller._retry_after = 0.0
                dev.updateStateOnServer("controllerAddress", entry.ip)
                self.store["next_poll"][dev.id] = 0.0
            elif mac in before and before[mac] != entry.ip:
                self.store["next_poll"][dev.id] = 0.0

    def _poll_device(self, dev, force=False):
        controller = self.store["controllers"].get(dev.id)
        if controller is None:
            return
        if not controller.ip:
            # Keep looking. A controller that did not answer the sweep at
            # startup was previously dead until the next re-check fifteen
            # minutes later, or until somebody noticed and edited the device.
            if not self._try_to_find_address(dev, controller):
                self.store["next_poll"][dev.id] = self._now() + self.poll_interval
                return
        state = controller.read_state(force=force)
        self.store["next_poll"][dev.id] = self._now() + self.poll_interval
        self._publish(dev, state, controller)

    # -- state publishing ---------------------------------------------------

    def _publish(self, dev, state, controller):
        """Write what the controller said onto the Indigo device.

        A missing state is written as unknown, never as a value. An unanswered
        query says "I do not know", and recording that as "off" would invent a
        reading nobody took.
        """
        if state is None:
            if dev.states.get("online", False):
                self.logger.warning(f"\"{dev.name}\" stopped answering — {controller.last_error}")
            dev.updateStateOnServer("online", False)
            dev.updateStateOnServer("mode", "unknown")
            dev.setErrorStateOnServer("offline")
            return

        if not dev.states.get("online", False):
            self.logger.info(f"\"{dev.name}\" is answering on {controller.ip}")
        dev.setErrorStateOnServer("")

        model = state.model
        runner = self.store["effects"].get(dev.id)

        if state.is_preset:
            mode = f"Pattern: {state.preset_name}"
        elif state.mode == proto.MODE_CUSTOM:
            mode = "Custom pattern"
        elif state.is_white_mode:
            mode = "White"
        else:
            mode = "Colour"

        updates = [
            {"key": "onOffState",        "value": state.is_on},
            {"key": "brightnessLevel",   "value": state.brightness_percent},
            {"key": "online",            "value": True},
            {"key": "mode",              "value": mode},
            {"key": "controllerModel",   "value": f"{model.name} ({model.channels})"},
            {"key": "controllerAddress", "value": controller.ip},
            {"key": "effect",            "value": (runner.name if runner and runner.running
                                                   else "none")},
        ]
        # In white mode the controller reports its colour channels as zero,
        # because they genuinely are off. Publishing that wipes the light's
        # colour out of Indigo, and the colour picker then opens on a black
        # wheel with nothing to go back to.
        #
        # So the last colour is kept instead. It is a setting rather than a
        # measurement — what the light would show if you asked for colour again
        # — and `mode` says "White" plainly, so nothing here claims the red
        # emitter is lit. It also matches what every other colour light in the
        # house does: a Zigbee bulb sitting in colour-temp mode keeps its RGB
        # values rather than reporting zeros.
        keep_last_colour = state.is_white_mode and not any(state.rgb)

        channels = [("whiteLevel", state.white)]
        if not keep_last_colour:
            channels += [("redLevel",   state.red),
                         ("greenLevel", state.green),
                         ("blueLevel",  state.blue)]
        for key, value in channels:
            if key in dev.states:
                updates.append({"key": key, "value": to_percent(value)})

        dev.updateStatesOnServer(updates)

        if any(state.rgb):
            self.store["hue"][dev.id] = self._normalise_hue(state.rgb)

    @staticmethod
    def _normalise_hue(rgb):
        """Scale a colour up so its strongest channel is full.

        This is a cache of the colour's HUE, kept so the brightness slider can
        dim and restore it without drifting. The device states remain the
        single record of what the lights are actually showing.
        """
        peak = max(rgb)
        if not peak:
            return (255, 255, 255)
        return tuple(min(255, int(round(c * 255.0 / peak))) for c in rgb)

    # -- helpers used by actions -------------------------------------------

    def _controller(self, dev):
        controller = self.store["controllers"].get(dev.id)
        if controller is None:
            self.logger.error(f"\"{dev.name}\" is not started — nothing to send to")
        return controller

    def _stop_effect(self, dev, reason=""):
        """Any manual command wins over a running effect."""
        runner = self.store["effects"].get(dev.id)
        if runner is not None and runner.running:
            self.logger.debug(f"Stopping effect {runner.name!r} on \"{dev.name}\" {reason}")
            runner.stop()
            dev.updateStateOnServer("effect", "none")

    def _start_effect(self, dev, name, steps):
        runner = self.store["effects"].get(dev.id)
        controller = self._controller(dev)
        if runner is None or controller is None:
            return False
        if not controller.ip:
            self.logger.error(f"\"{dev.name}\" has no address — cannot start {name}")
            return False

        # While an effect runs the plugin knows exactly what it is showing, so
        # it says so rather than leaving the device stale until the next poll.
        # Throttled, because a fade sends twenty steps a second and writing all
        # of them to the server would be twenty state writes a second for a
        # number nobody can read that fast.
        last_published = [0.0]

        def stepped(step):
            now = self._now()
            if now - last_published[0] < EFFECT_PUBLISH_GAP:
                return
            last_published[0] = now
            self._publish_step(dev, step)

        def finished(completed):
            try:
                # Publish the LAST frame straight away, throttle or no
                # throttle. Without this the device sits showing a colour from
                # part way through the fade until the next poll corrects it —
                # measured at up to a couple of seconds of a reading that is
                # simply wrong rather than merely old.
                final = runner.last_step
                if final is not None:
                    self._publish_step(dev, final)
                dev.updateStateOnServer("effect", "none")
                self.store["next_poll"][dev.id] = 0.0     # re-read on the next tick
            except Exception:
                self.logger.exception(f"Tidying up after {name} on \"{dev.name}\" failed")

        runner.start(name, steps, on_finish=finished, on_step=stepped)
        dev.updateStateOnServer("effect", name)
        return True

    def _publish_step(self, dev, step):
        """Write what an effect is currently showing onto the device."""
        updates = []
        if step.rgb is not None:
            updates += [{"key": "redLevel",        "value": to_percent(step.rgb[0])},
                        {"key": "greenLevel",      "value": to_percent(step.rgb[1])},
                        {"key": "blueLevel",       "value": to_percent(step.rgb[2])},
                        {"key": "brightnessLevel", "value": to_percent(max(step.rgb))}]
        if step.white is not None:
            updates += [{"key": "whiteLevel",      "value": to_percent(step.white)},
                        {"key": "brightnessLevel", "value": to_percent(step.white)}]
        if updates:
            dev.updateStatesOnServer(updates)

    def _current_rgb(self, dev):
        controller = self.store["controllers"].get(dev.id)
        state = controller.last_state if controller is not None else None
        if state is not None:
            return state.rgb
        return tuple(to_byte(dev.states.get(k, 0))
                     for k in ("redLevel", "greenLevel", "blueLevel"))

    def _send_colour(self, dev, rgb, log_as=None):
        controller = self._controller(dev)
        if controller is None:
            return False
        if not controller.send(proto.colour(rgb[0], rgb[1], rgb[2],
                                            model_num=controller.model_num or 0x06)):
            self.logger.error(f"send \"{dev.name}\" {log_as or 'colour'} failed")
            return False
        self.store["hue"][dev.id] = self._normalise_hue(rgb)
        self.store["next_poll"][dev.id] = 0.0
        return True

    # -- Indigo device actions ---------------------------------------------

    def actionControlDevice(self, action, dev):
        # Every dispatch is traceable. Without this an action that falls off
        # the end of the chain below does nothing AND says nothing, which is
        # indistinguishable from Indigo never having called us at all — and
        # that ambiguity cost an afternoon.
        self.logger.debug(f"actionControlDevice \"{dev.name}\": "
                          f"deviceAction={action.deviceAction!r} "
                          f"actionValue={getattr(action, 'actionValue', None)!r}")
        controller = self._controller(dev)
        if controller is None:
            return

        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            self._stop_effect(dev, "for a manual on")
            if controller.turn_on():
                self.logger.info(f"sent \"{dev.name}\" on")
                dev.updateStateOnServer("onOffState", True)
                self.store["next_poll"][dev.id] = 0.0
            else:
                self.logger.error(f"send \"{dev.name}\" on failed")

        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            self._stop_effect(dev, "for a manual off")
            if controller.turn_off():
                self.logger.info(f"sent \"{dev.name}\" off")
                dev.updateStateOnServer("onOffState", False)
                self.store["next_poll"][dev.id] = 0.0
            else:
                self.logger.error(f"send \"{dev.name}\" off failed")

        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            self._stop_effect(dev, "for a manual toggle")
            wanted = not dev.onState
            if (controller.turn_on() if wanted else controller.turn_off()):
                self.logger.info(f"sent \"{dev.name}\" toggle")
                dev.updateStateOnServer("onOffState", wanted)
                self.store["next_poll"][dev.id] = 0.0
            else:
                self.logger.error(f"send \"{dev.name}\" toggle failed")

        elif action.deviceAction in (indigo.kDeviceAction.SetBrightness,
                                     indigo.kDeviceAction.BrightenBy,
                                     indigo.kDeviceAction.DimBy):
            if action.deviceAction == indigo.kDeviceAction.SetBrightness:
                target = as_int(action.actionValue, 0, 0, 100)
            elif action.deviceAction == indigo.kDeviceAction.BrightenBy:
                target = as_int(dev.brightness + as_int(action.actionValue), 0, 0, 100)
            else:
                target = as_int(dev.brightness - as_int(action.actionValue), 0, 0, 100)
            self._set_brightness(dev, target)

        elif action.deviceAction == indigo.kDeviceAction.SetColorLevels:
            self._set_colour_levels(dev, action.actionValue)

        elif action.deviceAction == indigo.kDeviceAction.RequestStatus:
            self._poll_device(dev, force=True)
            self.logger.info(f"sent \"{dev.name}\" status request")

        else:
            # Being asked to do something and quietly not doing it is the worst
            # available outcome: the user sees no effect and no explanation.
            self.logger.warning(
                f"\"{dev.name}\": no handler for device action "
                f"{action.deviceAction!r} — nothing was sent. Please report this "
                f"with what you were doing at the time.")

    def actionControlUniversal(self, action, dev):
        self.logger.debug(f"actionControlUniversal \"{dev.name}\": "
                          f"deviceAction={action.deviceAction!r}")
        if action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self._poll_device(dev, force=True)
            self.logger.info(f"sent \"{dev.name}\" status request")
        else:
            self.logger.warning(
                f"\"{dev.name}\": no handler for universal action "
                f"{action.deviceAction!r} — nothing was sent.")

    def _set_brightness(self, dev, target):
        """Dim by scaling the current colour, keeping its hue."""
        controller = self._controller(dev)
        if controller is None:
            return
        self._stop_effect(dev, "for a brightness change")

        if target <= 0:
            if controller.turn_off():
                self.logger.info(f"sent \"{dev.name}\" off")
                dev.updateStatesOnServer([{"key": "onOffState", "value": False},
                                          {"key": "brightnessLevel", "value": 0}])
                self.store["next_poll"][dev.id] = 0.0
            else:
                self.logger.error(f"send \"{dev.name}\" off failed")
            return

        state = controller.last_state
        white_mode = state.is_white_mode if state is not None else False

        if white_mode:
            level = to_byte(target)
            ok = controller.set_warm_white(level)
        else:
            hue = self.store["hue"].get(dev.id) or self._normalise_hue(self._current_rgb(dev))
            scaled = tuple(int(round(c * target / 100.0)) for c in hue)
            ok = controller.set_colour(*scaled)

        if not ok:
            self.logger.error(f"send \"{dev.name}\" set brightness to {target} failed")
            return

        if not dev.onState:
            controller.turn_on()
        self.logger.info(f"sent \"{dev.name}\" set brightness to {target}")
        dev.updateStatesOnServer([{"key": "onOffState", "value": True},
                                  {"key": "brightnessLevel", "value": target}])
        self.store["next_poll"][dev.id] = 0.0

    def _set_colour_levels(self, dev, action_values):
        controller = self._controller(dev)
        if controller is None:
            return
        self._stop_effect(dev, "for a colour change")

        current = self._current_rgb(dev)
        red   = to_byte(action_values["redLevel"])   if "redLevel"   in action_values else current[0]
        green = to_byte(action_values["greenLevel"]) if "greenLevel" in action_values else current[1]
        blue  = to_byte(action_values["blueLevel"])  if "blueLevel"  in action_values else current[2]

        white_asked = "whiteLevel" in action_values and dev.supportsWhite
        white = to_byte(action_values["whiteLevel"]) if white_asked else None

        # An RGBW controller shows either its colour channels or its white one.
        # Asking for white means white; asking for colour means colour. Sending
        # both where the model does not honour it produces neither.
        if white_asked and white and not any((red, green, blue)):
            ok = controller.set_warm_white(white)
            shown = f"white {to_percent(white)}"
        else:
            ok = controller.set_colour(red, green, blue)
            shown = f"{to_percent(red)}, {to_percent(green)}, {to_percent(blue)}"

        if not ok:
            self.logger.error(f"send \"{dev.name}\" set colour to {shown} failed")
            return

        if not dev.onState:
            controller.turn_on()
        self.logger.info(f"sent \"{dev.name}\" set colour to {shown}")
        self.store["hue"][dev.id] = self._normalise_hue((red, green, blue))
        self.store["next_poll"][dev.id] = 0.0

    # -- plugin actions -----------------------------------------------------

    def action_warm_white(self, action, dev):
        controller = self._controller(dev)
        if controller is None:
            return
        self._stop_effect(dev, "for a white change")
        level = as_int(action.props.get("level", 100), 100, 0, 100)
        if controller.set_warm_white(to_byte(level)):
            if level and not dev.onState:
                controller.turn_on()
            self.logger.info(f"sent \"{dev.name}\" warm white {level}")
            self.store["next_poll"][dev.id] = 0.0
        else:
            self.logger.error(f"send \"{dev.name}\" warm white {level} failed")

    def action_cool_white(self, action, dev):
        controller = self._controller(dev)
        if controller is None:
            return
        self._stop_effect(dev, "for a white change")
        level = as_int(action.props.get("level", 100), 100, 0, 100)
        if controller.set_cool_white(to_byte(level)):
            if level and not dev.onState:
                controller.turn_on()
            self.logger.info(f"sent \"{dev.name}\" cool white {level}")
            self.store["next_poll"][dev.id] = 0.0
        else:
            self.logger.error(f"send \"{dev.name}\" cool white {level} failed")

    def action_preset(self, action, dev):
        controller = self._controller(dev)
        if controller is None:
            return
        self._stop_effect(dev, "for a built-in pattern")
        pattern = as_int(action.props.get("pattern", 0x25), 0x25)
        speed   = as_int(action.props.get("speed", 50), 50, 0, 100)
        if pattern not in proto.PRESETS:
            self.logger.error(f"\"{dev.name}\": 0x{pattern:02x} is not a pattern this "
                              f"controller knows")
            return
        if not dev.onState:
            controller.turn_on()
        if controller.set_preset(pattern, speed):
            self.logger.info(f"sent \"{dev.name}\" pattern \"{proto.PRESETS[pattern]}\" "
                             f"at speed {speed}")
            self.store["next_poll"][dev.id] = 0.0
        else:
            self.logger.error(f"send \"{dev.name}\" pattern failed")

    def action_custom_pattern(self, action, dev):
        controller = self._controller(dev)
        if controller is None:
            return
        self._stop_effect(dev, "for a custom pattern")
        colours = parse_palette(action.props.get("palette", ""))
        if not colours:
            self.logger.error(f"\"{dev.name}\": no usable colours in that palette — "
                              f"use R,G,B triples separated by a slash")
            return
        speed = as_int(action.props.get("speed", 30), 30, 0, 100)
        if not dev.onState:
            controller.turn_on()
        if controller.set_custom_pattern(colours, speed,
                                         action.props.get("transition", "gradual")):
            self.logger.info(f"sent \"{dev.name}\" a custom pattern of {len(colours)} colour(s)")
            self.store["next_poll"][dev.id] = 0.0
        else:
            self.logger.error(f"send \"{dev.name}\" custom pattern failed")

    def action_fade(self, action, dev):
        controller = self._controller(dev)
        if controller is None:
            return
        target = (as_int(action.props.get("red", 0), 0, 0, 255),
                  as_int(action.props.get("green", 0), 0, 0, 255),
                  as_int(action.props.get("blue", 0), 0, 0, 255))
        duration = as_float(action.props.get("duration", 5), 5.0, 0.0, 86400.0)
        ease     = action.props.get("ease", "smooth")

        if not dev.onState and any(target):
            controller.set_colour(0, 0, 0)
            controller.turn_on()

        plan = fx.plan_fade(self._current_rgb(dev), target, duration,
                            fps=self.effect_fps, ease=ease)
        if self._start_effect(dev, "fade", plan):
            self.logger.info(f"\"{dev.name}\" fading to {target} over {duration:g}s")

    def action_drift(self, action, dev):
        if self._controller(dev) is None:
            return
        palette = parse_palette(action.props.get("palette", ""))
        if not palette:
            self.logger.error(f"\"{dev.name}\": no usable colours in that palette — "
                              f"use R,G,B triples separated by a slash")
            return
        hold = as_float(action.props.get("hold", 120), 120.0, 0.0, 86400.0)
        fade = as_float(action.props.get("fade", 20), 20.0, 0.0, 3600.0)

        if not dev.onState:
            self.store["controllers"][dev.id].turn_on()

        plan = fx.plan_drift(palette, hold=hold, fade=fade, fps=self.effect_fps)
        if self._start_effect(dev, "drift", plan):
            self.logger.info(f"\"{dev.name}\" drifting through {len(palette)} colours, "
                             f"{hold:g}s each with a {fade:g}s crossfade")

    def action_sunrise(self, action, dev):
        controller = self._controller(dev)
        if controller is None:
            return
        duration = as_float(action.props.get("duration", 900), 900.0, 1.0, 86400.0)
        finish_white = as_bool(action.props.get("finishWhite", True), True)

        controller.set_colour(0, 0, 0)
        controller.turn_on()

        plan = fx.plan_sunrise(duration, fps=self.effect_fps,
                               peak_white=255 if finish_white else None)
        if self._start_effect(dev, "sunrise", plan):
            self.logger.info(f"\"{dev.name}\" starting a {describe_span(duration)} sunrise")

    def action_flash(self, action, dev):
        if self._controller(dev) is None:
            return
        rgb = (as_int(action.props.get("red", 255), 255, 0, 255),
               as_int(action.props.get("green", 0), 0, 0, 255),
               as_int(action.props.get("blue", 0), 0, 0, 255))
        times = as_int(action.props.get("times", 3), 3, 1, 20)
        restore = self._current_rgb(dev) if as_bool(action.props.get("restore", True), True) else None

        if not dev.onState:
            self.store["controllers"][dev.id].turn_on()

        plan = fx.plan_flash(rgb, times=times, restore_rgb=restore)
        if self._start_effect(dev, "flash", plan):
            self.logger.info(f"\"{dev.name}\" flashing {times} time(s)")

    def action_stop_effect(self, action, dev):
        runner = self.store["effects"].get(dev.id)
        if runner is None or not runner.running:
            self.logger.info(f"\"{dev.name}\" has no effect running")
            return
        name = runner.name
        self._stop_effect(dev, "on request")
        self.logger.info(f"stopped \"{name}\" on \"{dev.name}\"")

    # -- demo ---------------------------------------------------------------

    def magic_home_devices(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Dynamic list of this plugin's devices, for the demo picker."""
        rows = [(str(dev.id), dev.name)
                for dev in indigo.devices.iter("self.magicHomeLight") if dev.enabled]
        return rows or [("", "No MagicHome devices yet")]

    def _demo_plan(self, state):
        """The demo, as a list of steps, ending back where it started.

        Built as an ordinary effect plan so it inherits everything the runner
        already does — accurate pacing, stopping the moment a manual command
        arrives, and publishing what it is showing as it goes.

        The order is chosen to show the things that are actually worth seeing:
        the three colour channels one at a time (which is also how you spot a
        strip wired in the wrong channel order), then BOTH whites one after the
        other, because the difference between them is the single most
        surprising thing about this hardware.
        """
        beat = 1.2
        plan = [
            fx.Step(rgb=(255, 0, 0), white=None, hold=beat),
            fx.Step(rgb=(0, 255, 0), white=None, hold=beat),
            fx.Step(rgb=(0, 0, 255), white=None, hold=beat),
            fx.Step(rgb=None, white=255, hold=beat * 1.4),          # warm white
            fx.Step(rgb=(255, 255, 255), white=None, hold=beat * 1.4),  # cool white
        ]
        plan += fx.plan_fade((255, 255, 255), (255, 140, 60), 5.0,
                             fps=self.effect_fps, ease="smooth")
        plan.append(fx.Step(rgb=(255, 140, 60), white=None, hold=beat))

        # Put it back exactly as it was. A demo that leaves the lights on some
        # other colour has made work for whoever ran it.
        if state is not None:
            if state.is_white_mode:
                plan.append(fx.Step(rgb=None, white=state.white, hold=0.0))
            else:
                plan.append(fx.Step(rgb=state.rgb, white=None, hold=0.0))
        return plan

    def _start_demo(self, dev):
        controller = self.store["controllers"].get(dev.id)
        if controller is None or not controller.ip:
            self.logger.error(f"\"{dev.name}\" has no address — nothing to demo")
            return False

        state = controller.read_state(force=True)
        if state is None:
            self.logger.error(f"\"{dev.name}\" is not answering — "
                              f"nothing to demo ({controller.last_error})")
            return False

        was_on = state.is_on
        plan   = self._demo_plan(state)
        length = sum(step.hold for step in plan)

        self.logger.info(f"Demo on \"{dev.name}\" — red, green, blue, warm white, "
                         f"cool white, then a fade. About {length:.0f} seconds. "
                         f"Any command to the light stops it.")
        if not was_on:
            controller.turn_on()

        def finished(completed):
            # Only put it back off if the demo actually reached the end. A demo
            # stopped half way was stopped by somebody wanting the light on.
            try:
                if completed and not was_on:
                    controller.turn_off()
                self.store["next_poll"][dev.id] = 0.0
                if completed:
                    self.logger.info(f"Demo on \"{dev.name}\" finished — "
                                     f"put back as it was")
            except Exception:
                self.logger.exception("Tidying up after the demo failed")

        runner = self.store["effects"].get(dev.id)
        if runner is None:
            return False
        runner.stop()
        runner.start("demo", plan, on_finish=finished,
                     on_step=lambda step: self._publish_step(dev, step))
        dev.updateStateOnServer("effect", "demo")
        return True

    def run_demo(self, valuesDict=None, typeId="", devId=0):
        """The Run Demo button in the plugin's Configure dialog.

        Returns immediately. A config dialog callback that blocks for the
        length of the demo would hit Indigo's callback timeout and leave the
        dialog looking hung — the work belongs on the runner's own thread.
        """
        values = valuesDict if valuesDict is not None else {}
        dev_id = as_int(values.get("demoDevice"), 0)
        if not dev_id or dev_id not in indigo.devices:
            self.logger.error("Pick a light to demo first")
            return values
        self._start_demo(indigo.devices[dev_id])
        return values

    def run_demo_menu(self, valuesDict=None, typeId=None):
        """Plugins -> MagicHome -> Run Demo. Demos every light in turn."""
        devices = [d for d in indigo.devices.iter("self.magicHomeLight") if d.enabled]
        if not devices:
            self.logger.warning("No MagicHome devices to demo")
            return
        for dev in devices:
            self._start_demo(dev)

    # -- menu items ---------------------------------------------------------

    def discover_controllers_menu(self, valuesDict=None, typeId=None):
        found = self._refresh_discovery()
        if not found:
            self.logger.warning("No controllers answered. They must be on the same subnet "
                                "as the Indigo server, and powered on.")
            return
        self.logger.info(f"Found {len(found)} controller(s):")
        for entry in found:
            self.logger.info(f"    {entry.name}  {entry.ip}  {entry.mac}")

    def _banner_extras(self):
        """Extra banner lines, as (label, value) PAIRS.

        plugin_utils unpacks these with `for label, value in extras`, so a
        list of pre-formatted strings makes it try to unpack a string into two
        names and throw. The contract is in its docstring; I passed strings
        without reading it, and both this and Show Plugin Info died on the
        first click.
        """
        return [
            ("Poll interval:",    f"{self.poll_interval}s"),
            ("Effect rate:",      f"{self.effect_fps}/second"),
            ("Controllers seen:", str(len(self.store["discovered"]))),
            ("Devices:",          str(len(list(indigo.devices.iter("self.magicHomeLight"))))),
        ]

    def test_connection(self, valuesDict=None, typeId=None):
        # Full environment first, then the result — one log dump that can be
        # pasted straight into a support post.
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion,
                               extras=self._banner_extras())

        devices = list(indigo.devices.iter("self.magicHomeLight"))
        if not devices:
            self.logger.warning("No MagicHome devices defined yet")
            return

        for dev in devices:
            controller = self.store["controllers"].get(dev.id)
            if controller is None or not controller.ip:
                self.logger.error(f"\"{dev.name}\" — FAILED, no address")
                continue
            state = controller.read_state(force=True)
            if state is None:
                self.logger.error(f"\"{dev.name}\" — FAILED at {controller.ip}: "
                                  f"{controller.last_error}")
                continue
            model = state.model
            self.logger.info(
                f"\"{dev.name}\" — PASSED at {controller.ip}: {model.name} ({model.channels}), "
                f"firmware v{state.version}, "
                f"{'on' if state.is_on else 'off'}, RGB {state.rgb}, white {state.white}")

    def showPluginInfo(self, valuesDict=None, typeId=None):
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion,
                               extras=self._banner_extras())
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion}")
