---
title: Your lights
nav_order: 3
---

# Your lights

Each controller you add becomes one Indigo device of the kind **Magic Home Light**. This page explains what it shows and how its colours work.

## Controlling it

A Magic Home Light is an ordinary Indigo dimmer with colour. You control it with Indigo's usual **Turn On**, **Turn Off**, **Toggle**, brightness and colour controls, from the device list, a control page, a schedule, a trigger or an action group. The plugin's own actions for patterns and effects are on the [Actions and effects](actions.md) page.

- **Brightness** dims the colour that is showing and keeps its shade, so dimming to 30 and going back to 100 returns you to the colour you started with. When the light is showing white, brightness sets the white level.
- **Setting the brightness to 0** switches the light off.
- **Choosing a colour or a brightness while the light is off** switches it on.
- **Any of these stops an effect** the plugin is running on that light, so reaching for the brightness slider always wins.

## What it shows in Indigo

| Shown as | What it means |
|---|---|
| **On / Off and brightness** | Whether the light is on, and how bright, as the controller last reported it. |
| **Red, green, blue and white levels** | Each colour channel, from 0 to 100. |
| **Controller Model** | The kind of controller it reported itself as, such as `Controller RGBW (RGBW)`. The part in brackets is its colour channels. |
| **IP Address** | The network address the controller was last found at. |
| **Online** | Whether the controller answered the last check. |
| **Mode** | What the light is doing: **Colour**, **White**, **Custom pattern**, **Pattern:** followed by the name of a built-in pattern, or **unknown** when the controller is not answering. |
| **Running Effect** | The plugin effect running on the light — **fade**, **drift**, **sunrise**, **flash** or **demo** — or **none**. |

The plugin asks each controller what it is doing every 15 seconds to start with, or as often as the light's own **Check the controller every** setting says, and again straight after every command. While an effect runs, the light's colour in Indigo follows the effect as it goes.

When a controller shows white, it reports its colour channels as zero. The plugin keeps the last colour in Indigo instead, so the colour picker opens on that colour rather than on black, and **Mode** says **White**.

## Warm white and cool white

An RGBW controller — red, green, blue and white — has **one** white channel, and it is the warm one. What the Magic Home app calls cool white is red, green and blue turned up together, as there is no second white channel to use. The plugin does the same, and gives you **Set Warm White** and **Set Cool White** as separate actions so you can choose. The light's **"White" on this fixture means** setting decides which of the two Indigo's own white slider gives.

On a controller with two white channels, such as an RGBWW controller, **Set Cool White** uses the second white channel.

Most RGBW controllers, including the one I wrote this for, show their colour channels **or** their white channel, never both at once. If you ask for white with red, green and blue all at zero, you get the white the light is set to use. If you ask for any colour, you get the colour, and the first time you ask one of these lights for colour and white together, the Event Log says why only the colour came on.

## Which controllers it knows

The plugin reads the kind of controller from the controller itself, tells Indigo which colour channels it has, and adjusts what it sends to suit. It knows these kinds, as they appear in **Controller Model**:

| Controller Model | Channels |
|---|---|
| Controller RGBW | red, green, blue and white |
| Controller RGBWW | red, green, blue and two whites |
| Controller RGBCW | red, green, blue and two whites |
| Controller RGB | red, green and blue |
| Bulb RGBW | red, green, blue and white |
| Bulb RGBWW | red, green, blue and two whites |
| Dimmable white bulb | white only |
| Warm white controller | white only |
| Legacy controller | red, green and blue, for the oldest controllers |

I have tested it on one of these, an FVTLED **Controller RGBW**. The others come from the known details of each kind rather than from hardware on my bench.

A controller the plugin does not recognise is treated as an RGBW controller, which is the commonest kind, and the Event Log says so, so you know it has guessed.

## When a controller cannot be reached

If a controller stops answering, the light shows **offline** in red in the device list, **Online** turns off, **Mode** shows **unknown**, and the Event Log has one warning saying so. The on and off state is left as it was, because a controller that does not answer has not said it is off. The red stays until the controller answers again, even if an effect is running or you send the light a command in the meantime. When it answers, the red clears and the log says it is back, with its address.

A light that has never been found — one set to discovery whose controller did not answer — shows **no address** in red until the plugin finds it.

The [How it works](how-it-works.md) page explains how the plugin keeps looking.
