#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    make_icon.py
# Description: Generate the Plugin Store icon for MagicHome.
#              Follows the house style set by HoneywellEnvisalink and
#              Zigbee2MQTTBridge — rounded square, deep navy gradient, cyan
#              accents, brand above a rule, motif in the middle, hardware name
#              below.
#
#              The motif is an RGBW strip: a controller body feeding a length
#              of tape with four emitters — red, green, blue and a warm white —
#              washing colour onto the surface below. That is deliberately what
#              the hardware IS rather than a generic light bulb, and the fourth
#              emitter being warm rather than cool is the whole quirk of these
#              controllers: there is one white channel and it is the warm one.
#
#              No manufacturer logo is reproduced. "Zengge" appears as plain
#              text, naming the hardware the way ENVISALINK does on the
#              Honeywell icon.
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026
# Version:     1.0

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 512
SS   = 4                        # supersample factor for clean curves
W    = SIZE * SS

NAVY_TOP    = (14, 42, 74)
NAVY_BOTTOM = (10, 26, 48)
CYAN        = (94, 214, 233)
WHITE       = (240, 248, 255)
EDGE        = (72, 132, 180)

# The four channels, in the order they sit on the wire: R, G, B, then the
# single warm white.
RED   = (255, 62, 62)
GREEN = (74, 222, 106)
BLUE  = (86, 132, 255)
WARM  = (255, 214, 152)
CHANNELS = [RED, GREEN, BLUE, WARM]

STRIP_BODY = (34, 52, 78)
STRIP_EDGE = (86, 140, 190)

FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf",
]


def font(idx, px):
    return ImageFont.truetype(FONTS[idx], px)


def centred(draw, y, text, fnt, fill, tracking=0):
    """Draw horizontally-centred text, optionally letter-spaced."""
    if tracking:
        widths = [draw.textlength(ch, font=fnt) for ch in text]
        total  = sum(widths) + tracking * (len(text) - 1)
        x = (W - total) / 2
        for ch, adv in zip(text, widths):
            draw.text((x, y), ch, font=fnt, fill=fill)
            x += adv + tracking
    else:
        draw.text(((W - draw.textlength(text, font=fnt)) / 2, y), text,
                  font=fnt, fill=fill)


# ── Background: vertical gradient ───────────────────────────────────────────
bg = Image.new("RGB", (W, W), NAVY_BOTTOM)
grad = ImageDraw.Draw(bg)
for y in range(W):
    t = y / (W - 1)
    grad.line([(0, y), (W, y)],
              fill=tuple(int(NAVY_TOP[i] + (NAVY_BOTTOM[i] - NAVY_TOP[i]) * t)
                         for i in range(3)))

card = bg.convert("RGBA")

# ── Geometry ────────────────────────────────────────────────────────────────
STRIP_Y  = W * 0.500
LEFT     = W * 0.190
RIGHT    = W * 0.810
SPAN     = RIGHT - LEFT
positions = [LEFT + SPAN * (0.5 + i) / len(CHANNELS) for i in range(len(CHANNELS))]


def glow_layer(shapes, blur, strength):
    """Build a glow on its own layer and composite it.

    ImageDraw does NOT blend — an RGBA fill with a low alpha REPLACES the
    pixels underneath, punching a translucent hole instead of adding light.
    Glows therefore have to be drawn opaque on a transparent layer, blurred,
    faded through the alpha channel, and composited.
    """
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for box, colour in shapes:
        ld.ellipse(box, fill=colour + (255,))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    layer.putalpha(layer.split()[3].point(lambda v: int(v * strength)))
    return layer


# ── The colour each emitter throws onto the surface below ───────────────────
# Separate pools in their own colours which add where they overlap, because
# that is what light actually does on a wall.
pools = []
for x, colour in zip(positions, CHANNELS):
    spread = W * 0.140
    pools.append(([x - spread, STRIP_Y + W * 0.015,
                   x + spread, STRIP_Y + W * 0.265], colour))
card = Image.alpha_composite(card, glow_layer(pools, W * 0.062, 0.58))

# A tighter, brighter core just under the tape.
cores = []
for x, colour in zip(positions, CHANNELS):
    spread = W * 0.052
    cores.append(([x - spread, STRIP_Y, x + spread, STRIP_Y + W * 0.085], colour))
card = Image.alpha_composite(card, glow_layer(cores, W * 0.022, 0.75))

# ── The emitters' own bloom, above the tape ─────────────────────────────────
blooms = []
for x, colour in zip(positions, CHANNELS):
    r = W * 0.062
    blooms.append(([x - r, STRIP_Y - r, x + r, STRIP_Y + r], colour))
card = Image.alpha_composite(card, glow_layer(blooms, W * 0.028, 0.85))

d = ImageDraw.Draw(card)

# ── The tape itself ─────────────────────────────────────────────────────────
half_h = W * 0.047
d.rounded_rectangle([LEFT, STRIP_Y - half_h, RIGHT, STRIP_Y + half_h],
                    radius=half_h * 0.5, fill=STRIP_BODY + (255,),
                    outline=STRIP_EDGE + (235,), width=int(W * 0.0055))

# Cut lines and solder pads, so it reads as LED tape rather than a bar.
for i in range(1, len(CHANNELS)):
    px = LEFT + SPAN * i / len(CHANNELS)
    d.line([(px, STRIP_Y - half_h), (px, STRIP_Y + half_h)],
           fill=(52, 80, 116, 255), width=int(W * 0.004))
    pad_w, pad_h = W * 0.010, W * 0.020
    for side in (-1, 1):
        d.rectangle([px + side * W * 0.014 - pad_w / 2, STRIP_Y - pad_h / 2,
                     px + side * W * 0.014 + pad_w / 2, STRIP_Y + pad_h / 2],
                    fill=(62, 94, 132, 255))

# ── The four emitters ───────────────────────────────────────────────────────
led_r = W * 0.032
for x, colour in zip(positions, CHANNELS):
    d.ellipse([x - led_r, STRIP_Y - led_r, x + led_r, STRIP_Y + led_r],
              fill=colour + (255,), outline=WHITE + (225,), width=int(W * 0.0035))
    hi = led_r * 0.30
    d.ellipse([x - led_r * 0.30 - hi, STRIP_Y - led_r * 0.30 - hi,
               x - led_r * 0.30 + hi, STRIP_Y - led_r * 0.30 + hi],
              fill=WHITE + (200,))

# ── Text ────────────────────────────────────────────────────────────────────
centred(d, W * 0.088, "MAGIC HOME", font(0, int(W * 0.108)), WHITE + (255,),
        tracking=W * 0.002)

rule_y = W * 0.232
d.line([(W * 0.225, rule_y), (W * 0.775, rule_y)], fill=CYAN + (220,),
       width=int(W * 0.007))

centred(d, W * 0.268, "WIFI LED CONTROL", font(1, int(W * 0.062)), CYAN + (245,),
        tracking=W * 0.011)

centred(d, W * 0.838, "ZENGGE", font(1, int(W * 0.082)), CYAN + (255,),
        tracking=W * 0.024)

# ── Rounded-square mask + edge ──────────────────────────────────────────────
mask = Image.new("L", (W, W), 0)
radius = int(W * 0.20)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, W - 1], radius=radius, fill=255)

icon = Image.new("RGBA", (W, W), (0, 0, 0, 0))
icon.paste(card, (0, 0), mask)

inset = int(W * 0.012)
ImageDraw.Draw(icon).rounded_rectangle(
    [inset, inset, W - 1 - inset, W - 1 - inset], radius=radius - inset,
    outline=EDGE + (170,), width=int(W * 0.008))

icon = icon.resize((SIZE, SIZE), Image.LANCZOS)

import os
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "MagicHome.indigoPlugin", "Contents", "Resources", "icon.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
icon.save(out)
print("wrote", os.path.normpath(out), icon.size, icon.mode)
