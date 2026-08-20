#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    magichome_protocol.py
# Description: Pure wire protocol for Zengge / Magic Home WiFi LED controllers
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.0
#
# This module is DELIBERATELY free of Indigo and of sockets. Everything here is
# a pure function over bytes, so the whole protocol can be tested without a
# controller and without a server. The transport lives in magichome_device.py.
#
# Every fact below was measured against a live FVTLED / Zengge RGBW controller
# (hardware AK001-ZJ21413, model byte 0x06, firmware v4) on 20-08-2026, and
# cross-checked against the flux_led library. Where the two disagreed, the live
# controller won.

from collections import namedtuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTROL_PORT     = 5577          # TCP, takes commands and answers queries
DISCOVERY_PORT   = 48899         # UDP, broadcast discovery + wifi config
DISCOVERY_PROBE  = b"HF-A11ASSISTHREAD"

STATE_FRAME_LEN  = 14            # reply to QUERY_STATE
STATE_FRAME_HEAD = 0x81

QUERY_STATE      = bytes([0x81, 0x8A, 0x8B, 0x96])   # already checksummed

POWER_ON         = 0x23
POWER_OFF        = 0x24

# Write mask on a colour message: which half of the fixture the message applies to.
MASK_COLOUR      = 0xF0          # RGB channels only, leave white alone
MASK_WHITE       = 0x0F          # white channel(s) only, leave RGB alone
MASK_BOTH        = 0x00          # both at once (not honoured by every model)

MAX_DELAY        = 0x1F          # slowest preset step

# Preset patterns. These run ON the controller — fire one command and the
# network goes quiet. Codes are contiguous 0x25..0x38.
PRESETS = {
    0x25: "Seven colour cross fade",
    0x26: "Red gradual change",
    0x27: "Green gradual change",
    0x28: "Blue gradual change",
    0x29: "Yellow gradual change",
    0x2A: "Cyan gradual change",
    0x2B: "Purple gradual change",
    0x2C: "White gradual change",
    0x2D: "Red/green cross fade",
    0x2E: "Red/blue cross fade",
    0x2F: "Green/blue cross fade",
    0x30: "Seven colour strobe",
    0x31: "Red strobe",
    0x32: "Green strobe",
    0x33: "Blue strobe",
    0x34: "Yellow strobe",
    0x35: "Cyan strobe",
    0x36: "Purple strobe",
    0x37: "White strobe",
    0x38: "Seven colour jumping",
}

# Custom-pattern transition styles (a custom pattern is up to 16 colours held
# in the controller and cycled by it, with no further traffic).
TRANSITION_GRADUAL = 0x3A
TRANSITION_JUMP    = 0x3B
TRANSITION_STROBE  = 0x3C
TRANSITIONS = {
    "gradual": TRANSITION_GRADUAL,
    "jump":    TRANSITION_JUMP,
    "strobe":  TRANSITION_STROBE,
}
CUSTOM_PATTERN_SLOTS = 16

# Mode byte (state frame index 3) when the controller is not running a preset.
MODE_STATIC   = 0x61
MODE_CUSTOM   = 0x60
MODE_PRESET_LO, MODE_PRESET_HI = 0x25, 0x38

# ---------------------------------------------------------------------------
# Model table
# ---------------------------------------------------------------------------
# `msg_len` is the number of value bytes in a colour message and is the single
# most important field here: a wrong length does NOT raise an error, it gets
# misread as a different command entirely. Sending the 9-byte form to an 8-byte
# controller switched a live unit OFF during testing.
#
#   8  -> 31 R G B W <mask> 0f            (RGB and RGBW controllers)
#   9  -> 31 R G B W W2 <mask> 0f         (RGBWW / RGBCW controllers)
#   0  -> the pre-checksum original protocol, handled separately

Model = namedtuple("Model", "name channels msg_len has_white has_two_whites")

MODELS = {
    0x01: Model("Legacy controller",       "RGB",   0, False, False),
    0x04: Model("Controller RGBW",         "RGBW",  8, True,  False),
    0x06: Model("Controller RGBW",         "RGBW",  8, True,  False),
    0x07: Model("Controller RGBCW",        "RGBWW", 9, True,  True),
    0x21: Model("Dimmable white bulb",     "W",     8, True,  False),
    0x25: Model("Controller RGBWW",        "RGBWW", 9, True,  True),
    0x27: Model("Warm white controller",   "W",     9, True,  False),
    0x33: Model("Controller RGB",          "RGB",   8, False, False),
    0x35: Model("Bulb RGBWW",              "RGBWW", 9, True,  True),
    0x44: Model("Bulb RGBW",               "RGBW",  8, True,  False),
    0x81: Model("Controller RGBW",         "RGBW",  8, True,  False),
}

UNKNOWN_MODEL = Model("Unknown controller", "RGBW", 8, True, False)


def model_for(model_num):
    """Return the Model for a model byte, falling back to the 8-byte RGBW shape.

    The fallback is deliberate: 8-byte is the commonest form and the safe guess,
    but a caller that cares should check `is_known_model` and say so in the log
    rather than quietly pretending it recognised the hardware.
    """
    return MODELS.get(model_num, UNKNOWN_MODEL)


def is_known_model(model_num):
    return model_num in MODELS


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------

def checksum(payload):
    """The controller's checksum: a plain sum of every preceding byte."""
    return sum(payload) & 0xFF


def frame(payload):
    """Append the checksum and return the bytes to put on the wire."""
    payload = bytes(payload)
    return payload + bytes([checksum(payload)])


def _clamp_byte(value):
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(255, value))


def _clamp_percent(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, value))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def power(on, model_num=0x06):
    """Turn the controller on or off."""
    if model_for(model_num).msg_len == 0:
        return bytes([0xCC, POWER_ON if on else POWER_OFF, 0x33])
    return frame([0x71, POWER_ON if on else POWER_OFF, 0x0F])


def colour(red, green, blue, white=0, white2=0, model_num=0x06, mask=MASK_COLOUR):
    """Set the colour and/or white channels.

    `mask` decides which half of the fixture the message applies to. Use
    MASK_COLOUR for RGB, MASK_WHITE for white, MASK_BOTH only where the model
    is known to honour it.
    """
    red, green, blue = _clamp_byte(red), _clamp_byte(green), _clamp_byte(blue)
    white, white2    = _clamp_byte(white), _clamp_byte(white2)
    model            = model_for(model_num)

    if model.msg_len == 0:
        # The original protocol carries no white channel and no checksum.
        return bytes([0x56, red, green, blue, 0xAA])
    if model.msg_len == 9:
        return frame([0x31, red, green, blue, white, white2, mask, 0x0F])
    return frame([0x31, red, green, blue, white, mask, 0x0F])


def warm_white(level, model_num=0x06):
    """Drive the dedicated white channel, leaving RGB alone."""
    return colour(0, 0, 0, white=level, model_num=model_num, mask=MASK_WHITE)


def cool_white(level=255, model_num=0x06):
    """Cool white on an RGBW controller is the RGB trio at equal full level.

    Measured, not guessed: setting cool white in the Magic Home app puts
    R=G=B=255 with the white channel at 0. There is no second white channel on
    a model 0x06 — an RGBWW model has one and should use white2 instead.
    """
    model = model_for(model_num)
    if model.has_two_whites:
        return colour(0, 0, 0, white=0, white2=level,
                      model_num=model_num, mask=MASK_WHITE)
    level = _clamp_byte(level)
    return colour(level, level, level, model_num=model_num, mask=MASK_COLOUR)


def speed_to_delay(speed):
    """Convert a 0-100 speed into the controller's 1-31 delay byte."""
    speed = int(_clamp_percent(speed))
    delay = int(((100 - speed) * (MAX_DELAY - 1)) / 100) + 1
    return max(1, min(MAX_DELAY, delay))


def delay_to_speed(delay):
    """Inverse of speed_to_delay, for reporting what the controller is doing."""
    try:
        delay = int(delay)
    except (TypeError, ValueError):
        return 0
    delay = max(1, min(MAX_DELAY, delay))
    inv = int(((delay - 1) * 100) / (MAX_DELAY - 1))
    return max(0, min(100, 100 - inv))


def preset(pattern, speed=50):
    """Run one of the controller's built-in patterns."""
    pattern = int(pattern)
    if pattern not in PRESETS:
        raise ValueError(f"preset pattern must be one of {sorted(PRESETS)}, got 0x{pattern:02x}")
    return frame([0x61, pattern, speed_to_delay(speed), 0x0F])


def custom_pattern(rgb_list, speed=50, transition="gradual"):
    """Load up to 16 colours the controller will cycle by itself.

    Empty slots are padded with the (1, 2, 3) sentinel the firmware expects —
    padding with black would show as a blackout in the sequence.
    """
    if not rgb_list:
        raise ValueError("a custom pattern needs at least one colour")
    colours = list(rgb_list)[:CUSTOM_PATTERN_SLOTS]

    payload = bytearray()
    for index, (red, green, blue) in enumerate(colours):
        payload.extend([0x51 if index == 0 else 0x00,
                        _clamp_byte(red), _clamp_byte(green), _clamp_byte(blue)])
    for _ in range(CUSTOM_PATTERN_SLOTS - len(colours)):
        payload.extend([0x00, 0x01, 0x02, 0x03])

    payload.append(0x00)
    payload.append(speed_to_delay(speed))
    payload.append(TRANSITIONS.get(str(transition).lower(), TRANSITION_GRADUAL))
    payload.append(0xFF)
    payload.append(0x0F)
    return frame(payload)


def query():
    """The state query. Already carries its checksum."""
    return QUERY_STATE


# ---------------------------------------------------------------------------
# State parsing
# ---------------------------------------------------------------------------

class ControllerState(namedtuple(
        "ControllerState",
        "model_num is_on mode preset_code speed red green blue white white2 "
        "version write_mode raw")):
    """One decoded 14-byte state frame."""

    __slots__ = ()

    @property
    def model(self):
        return model_for(self.model_num)

    @property
    def is_preset(self):
        return MODE_PRESET_LO <= self.mode <= MODE_PRESET_HI

    @property
    def preset_name(self):
        return PRESETS.get(self.mode) if self.is_preset else None

    @property
    def is_white_mode(self):
        return self.write_mode == MASK_WHITE

    @property
    def rgb(self):
        return (self.red, self.green, self.blue)

    @property
    def brightness_percent(self):
        """Brightness as Indigo means it: 0-100, from whichever channels are lit.

        White mode reports the white channel; colour mode reports the strongest
        of R/G/B, which is how a colour picker's value component behaves.
        """
        if not self.is_on:
            return 0
        if self.is_white_mode:
            source = max(self.white, self.white2)
        else:
            source = max(self.red, self.green, self.blue)
        return int(round(source / 255.0 * 100.0))


def parse_state(data):
    """Decode a 14-byte state frame. Returns None if it is not a valid one.

    The checksum is verified. A frame that fails is rejected rather than
    guessed at, because these controllers push unsolicited state frames and a
    misaligned read produces bytes that look entirely plausible.
    """
    if data is None or len(data) < STATE_FRAME_LEN:
        return None
    data = bytes(data[:STATE_FRAME_LEN])
    if data[0] != STATE_FRAME_HEAD:
        return None
    if checksum(data[:STATE_FRAME_LEN - 1]) != data[STATE_FRAME_LEN - 1]:
        return None

    return ControllerState(
        model_num   = data[1],
        is_on       = data[2] == POWER_ON,
        mode        = data[3],
        preset_code = data[3] if MODE_PRESET_LO <= data[3] <= MODE_PRESET_HI else None,
        # Speed is only meaningful while a preset is running. Reporting a
        # number for it in static colour mode would be a number that means
        # nothing, which reads as a measurement.
        speed       = (delay_to_speed(data[5])
                       if MODE_PRESET_LO <= data[3] <= MODE_PRESET_HI else None),
        red         = data[6],
        green       = data[7],
        blue        = data[8],
        white       = data[9],
        version     = data[10],
        white2      = data[11],
        write_mode  = data[12],
        raw         = data,
    )


def find_state_frame(buffer, expect_model=None):
    """Pull the LAST valid state frame out of a buffer of mixed traffic.

    This is not defensive padding. These controllers push their own state
    unprompted, wrapped in a 0xb0 0xb1 0xb2 0xb3 header with a sequence number,
    so a socket carries frames nobody asked for. Assuming one reply per request
    produces readings that are pure noise but look like real values — it
    happened during development and every number was wrong. Always scan, always
    verify the checksum, and prefer the newest match. Pass `expect_model`
    once the model byte is known and stray matches stop being possible.
    """
    if not buffer:
        return None
    buffer = bytes(buffer)
    fallback = None
    for start in range(len(buffer) - STATE_FRAME_LEN, -1, -1):
        state = parse_state(buffer[start:start + STATE_FRAME_LEN])
        if state is None:
            continue
        if expect_model is None or state.model_num == expect_model:
            return state
        # Right shape, wrong controller: keep it only as a last resort. A push
        # frame's innards can coincidentally checksum, and once the model is
        # known that is the cheapest way to tell the two apart.
        if fallback is None:
            fallback = state
    return fallback


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

Discovered = namedtuple("Discovered", "ip mac hardware_id name")


def parse_discovery_reply(payload):
    """Decode one UDP discovery reply: '<ip>,<mac>,<hardware id>[,<uuid>]'."""
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8", errors="replace")
    parts = [p.strip() for p in payload.strip().split(",")]
    if len(parts) < 3 or not parts[0] or not parts[1]:
        return None
    ip, mac, hardware_id = parts[0], parts[1].upper(), parts[2]
    return Discovered(ip=ip, mac=mac, hardware_id=hardware_id,
                      name=friendly_name(mac, hardware_id))


def friendly_name(mac, hardware_id=""):
    """The name the Magic Home app shows is the last six of the MAC.

    Worth mirroring: it is how the controller is labelled in the app, so it is
    what anyone will recognise. It is NOT a model number, however much it looks
    like one.
    """
    tail = (mac or "").replace(":", "").replace("-", "").upper()[-6:]
    return f"{tail} ({hardware_id})" if hardware_id else tail


def normalise_mac(mac):
    """Reduce a MAC to bare uppercase hex so it can be used as a stable key."""
    if not mac:
        return ""
    return "".join(c for c in str(mac).upper() if c in "0123456789ABCDEF")
