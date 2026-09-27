---
title: Version history
nav_order: 9
---

# Version history

The newest version is at the top.

## 1.3.0 — 27 September 2026

A light that stops answering now stays marked **offline**, in red, until it answers again. Before, an effect running on it, or the plugin noticing it had moved to a new address, could clear the red while the light was still not answering, so the device list and Device Health Monitor could both show a dead light as fine.

## 1.2.0 — 27 September 2026

- The **"White" on this fixture means** setting on each light now does what it says. Set it to **Cool** and Indigo's white slider gives red, green and blue together, the way the Magic Home app does, instead of always using the warm white channel. The light then shows **White** as its mode, and its white level stays where you put it.
- The **Check the controller every** setting on each light now works. Before, every light was checked at the plugin's own rate whatever the box said. Leave the box blank and the light uses the plugin's **Default poll interval**. Lights you added before this version have 15 in the box, so they carry on at 15 seconds until you change it or empty it.
- **Flash** with **Put the previous colour back afterwards** ticked now puts a light that was showing white back on white. Before, it went dark.
- If you ask a light for colour and white together and the controller can only show one, it shows the colour as before, and the Event Log now says why, once for each light.

## 1.1.5 — 11 September 2026

The plugin carries a note of where its code lives on GitHub, the same way other Indigo plugins do. Nothing else changed.

## 1.1.4 — 31 August 2026

A line of unused code was removed. Nothing you would notice changed.

## 1.1.3 — 21 August 2026

- If Indigo asks a light to do something the plugin does not handle, the Event Log now says so, instead of nothing happening in silence.
- When a light first answers, the plugin tells Indigo which colour channels its controller has, so a controller with two white channels is set up with both.

## 1.1.2 — 21 August 2026

When a light shows white, Indigo keeps its last colour. Before, the colour channels went to zero, and the colour picker opened on black with nothing to go back to.

## 1.1.1 — 21 August 2026

**Test Connection** and **Show Plugin Info** work. Both stopped with an error on the first click before.

## 1.1.0 — 20 August 2026

New **Run Demo**, as a button in the Configure dialog for one light and as an item in the Plugins menu for every light. It shows red, green and blue one at a time, then warm white, cool white and a fade, and puts the light back exactly as it was.

## 1.0.1 — 20 August 2026

The plugin has its own icon for the Indigo Plugin Store.

## 1.0.0 — 20 August 2026

The first release.

- Each Magic Home controller becomes an Indigo dimmer with colour, found by the number it was made with, so a new network address from your router does not lose it.
- The controller's 20 built-in patterns, and custom patterns of up to 16 colours that the controller stores and cycles by itself.
- The plugin's own effects: fade, colour drift, sunrise and flash.
- Separate **Set Warm White** and **Set Cool White** actions.
