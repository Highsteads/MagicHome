---
title: Home
nav_order: 1
---

# Magic Home for Indigo

This plugin lets [Indigo](https://www.indigodomo.com) control the wifi LED controllers made by Zengge — the ones sold under names such as **Magic Home**, **Magic Hue**, **FVTLED** and **LEDENET**, and set up with the Magic Home Pro app. It talks to each controller directly over your home network, so there is no cloud account, no app running in the background and no password to store anywhere.

I wrote it for an FVTLED RGBW controller driving LED deck lights on shelves, and every command it sends has been checked against that controller.

## Check this first

These lights come in two kinds, and only one of them can be reached from Indigo.

**Turn Bluetooth off on your phone, stay on your home wifi, and open the Magic Home app.**

- **If the lights still work,** you have a wifi controller, and this plugin will drive it.
- **If the app cannot find them,** you have a Bluetooth-only controller. This plugin cannot reach it, and nor can any other Indigo plugin, because it is not on your network at all.

Some recent Zengge hardware — the `LEDnetWF` family and various controllers built on the BL602 chip — has no wifi control at all. There is no setting that turns it on.

## What it does for you

- **Makes each controller an ordinary Indigo dimmer,** so the brightness slider and colour picker work, along with control pages, triggers, schedules, and anything else that understands a dimmer, such as a HomeKit or Alexa bridge.
- **Finds each controller by the number it was made with,** so when your router gives it a new network address the plugin finds it again by itself.
- **Runs the controller's own 20 built-in patterns,** and loads your own pattern of up to 16 colours, which the controller stores and cycles by itself.
- **Adds effects the controller cannot do on its own** — a smooth fade to any colour, a slow drift around a set of colours, a sunrise over as many minutes as you like, and a short flash that puts the previous colour back.
- **Gives you warm white and cool white as separate actions,** because on these controllers they are two different things, as the [Your lights](devices.md) page explains.
- **Runs a short demo** that shows each colour channel and both whites in turn, then puts the light back as it was, so you can check a new strip is wired the way you expect.

## Where to go next

| If you want to... | Read |
|---|---|
| Install the plugin and add your first light | [Getting started](getting-started.md) |
| Know what each light shows in Indigo | [Your lights](devices.md) |
| Understand what the plugin is doing behind the scenes | [How it works](how-it-works.md) |
| Use the colour actions, patterns and effects | [Actions and effects](actions.md) |
| Know what every setting does | [Settings](settings.md) |
| Know what each item in the Plugins menu does | [The plugin menu](plugin-menu.md) |
| Sort out a problem | [When something goes wrong](when-something-goes-wrong.md) |
| See what changed in each version | [Version history](changelog.md) |
| Read the technical detail — the protocol, how the plugin is built, driving it from a Python script | [Technical notes](technical-notes.md) |

## Download

The latest version is always on the [Releases page](https://github.com/Highsteads/MagicHome/releases/latest).
