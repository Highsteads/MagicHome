#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    indigo_stub.py
# Description: Just enough of the Indigo module to import plugin.py under test
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.0
#
# Deliberately thin. It exists so the SHIPPED plugin.py can be imported and its
# real methods called — a re-implementation in the test file would only ever
# test the re-implementation.

import sys
import types


class _Enum(object):
    def __init__(self, **names):
        for key, value in names.items():
            setattr(self, key, value)


class FakeDevice(object):
    def __init__(self, dev_id=1, name="Shelf Lights", props=None, states=None):
        self.id            = dev_id
        self.name          = name
        self.pluginProps   = props if props is not None else {}
        self.states        = states if states is not None else {
            "onOffState": False, "brightnessLevel": 0, "online": False,
            "redLevel": 0, "greenLevel": 0, "blueLevel": 0, "whiteLevel": 0,
        }
        self.enabled       = True
        self.configured    = True
        self.errorState    = ""
        self.supportsWhite = True
        self.supportsRGB   = True
        self.updates       = []

    @property
    def onState(self):
        return bool(self.states.get("onOffState", False))

    @property
    def brightness(self):
        return int(self.states.get("brightnessLevel", 0))

    def updateStateOnServer(self, key, value, **kwargs):
        self.states[key] = value
        self.updates.append((key, value))

    def updateStatesOnServer(self, kv_list):
        for item in kv_list:
            self.updateStateOnServer(item["key"], item["value"])

    def setErrorStateOnServer(self, value):
        self.errorState = value


class _Devices(object):
    """Mimics indigo.devices closely enough to matter.

    Membership and subscript are both real behaviours the plugin relies on —
    and on a live server a membership test with an unknown id returns False
    rather than raising, which is what makes a guarded `in` check safe.
    """

    def __init__(self):
        self.all = []

    def iter(self, _filter=""):
        return list(self.all)

    def __iter__(self):
        return iter(self.all)

    def __contains__(self, key):
        return any(d.id == key for d in self.all)

    def __getitem__(self, key):
        for d in self.all:
            if d.id == key:
                return d
        raise KeyError(key)

    def __len__(self):
        return len(self.all)


def install():
    """Put a stub `indigo` module on sys.modules and return it."""
    mod = types.ModuleType("indigo")

    class PluginBase(object):
        def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
            import logging
            self.pluginId          = pluginId
            self.pluginDisplayName = pluginDisplayName
            self.pluginVersion     = pluginVersion
            self.pluginPrefs       = pluginPrefs or {}
            self.logger            = logging.getLogger("test.magichome")
            self.logger.addHandler(logging.NullHandler())
            self.logger.propagate  = False
            self.indigo_log_handler = _Enum(setLevel=lambda level: None)
            self.debug             = False

        def sleep(self, seconds):
            pass

        class StopThread(Exception):
            pass

    mod.PluginBase = PluginBase
    mod.Dict       = dict
    mod.List       = list
    mod.devices    = _Devices()
    mod.server     = _Enum(log=lambda *a, **k: None,
                           getInstallFolderPath=lambda: "/tmp")
    mod.kDeviceAction = _Enum(TurnOn="on", TurnOff="off", Toggle="toggle",
                              SetBrightness="setbright", BrightenBy="brighten",
                              DimBy="dim", SetColorLevels="setcolor",
                              RequestStatus="status")
    mod.kUniversalAction = _Enum(RequestStatus="status")
    sys.modules["indigo"] = mod
    return mod


class FakeAction(object):
    def __init__(self, device_action=None, action_value=None, props=None):
        self.deviceAction = device_action
        self.actionValue  = action_value
        self.props        = props or {}
