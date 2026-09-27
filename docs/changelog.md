---
title: Version history
nav_order: 9
---

# Version history

The newest version is at the top.

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
