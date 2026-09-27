# Magic Home for Indigo

**Control Magic Home wifi LED lights from Indigo, straight over your home network.**

**Version:** 1.1.5 | **Author:** CliveS & Claude | **Needs:** Indigo 2022.1 or later, and a Magic Home controller on your wifi

**[Read the full guide](https://highsteads.github.io/MagicHome/)** — setting up, what everything means, and what to do when something goes wrong.

---

## Check this first

These lights come in two kinds, and only one of them can be reached from Indigo.

**Turn Bluetooth off on your phone, stay on your home wifi, and open the Magic Home app.**

- **If the lights still work,** you have a wifi controller, and this plugin will drive it.
- **If the app cannot find them,** you have a Bluetooth-only controller. This plugin cannot reach it, and nor can any other Indigo plugin, because it is not on your network at all.

Some recent Zengge hardware — the `LEDnetWF` family and various controllers built on the BL602 chip — has no wifi control at all. There is no setting that turns it on.

## What it does

This plugin lets [Indigo](https://www.indigodomo.com) control the wifi LED controllers made by Zengge, sold under names such as **Magic Home**, **Magic Hue**, **FVTLED** and **LEDENET**, and set up with the Magic Home Pro app. It talks to each one directly over your home network, so there is no cloud account, no app running in the background and no password to store.

- **Makes each controller an ordinary Indigo dimmer,** so the brightness slider and colour picker work, along with control pages, triggers, schedules and anything else that understands a dimmer.
- **Finds each controller by the number it was made with,** so when your router gives it a new network address the plugin finds it again by itself.
- **Runs the controller's own 20 built-in patterns,** and loads your own pattern of up to 16 colours, which the controller stores and cycles by itself.
- **Adds effects the controller cannot do on its own** — a smooth fade, a slow drift round a set of colours, a sunrise over as many minutes as you like, and a short flash that puts the previous colour back.
- **Gives you warm white and cool white as separate actions.** An RGBW controller has one white channel, the warm one, and the app makes cool white by turning red, green and blue up together. The plugin does the same, so you can choose.
- **Runs a short demo** of each colour channel and both whites, then puts the light back as it was, so you can check a new strip is wired the way you expect.

## Which controllers it works with

Any Magic Home controller on your wifi — strip controllers, bulbs and the controllers sold with deck-light kits. The plugin reads the kind of controller from the controller itself and adjusts what it sends to suit. I wrote it for an FVTLED RGBW controller and have tested it on that one. A controller it does not recognise is treated as the commonest kind, RGBW, and the Event Log says so.

## Installing

1. Go to the [Releases page](https://github.com/Highsteads/MagicHome/releases/latest) and download `MagicHome.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `MagicHome.indigoPlugin`
3. Double-click `MagicHome.indigoPlugin` — Indigo will install it automatically

## Setting it up

1. Choose **Plugins → MagicHome → Discover Controllers**. Every controller on the same part of your network as Indigo is listed in the Event Log.
2. Create a **New Device**, choose **MagicHome** and **Magic Home Light**, leave **Find the controller by** on **Discovery**, and pick your controller from the list. It is named by the last six characters of its MAC address, the same way the Magic Home app names it.
3. Click **Save**, and the light shows its state within a few seconds.
4. Open **Plugins → MagicHome → Configure**, choose the light under **Demo this light** and click **Run Demo** to see it show each colour and both whites.

The [full guide](https://highsteads.github.io/MagicHome/) goes through each step, explains every setting and action, and covers what to do if something does not work.

## What's new

**v1.1.5** — The plugin carries a note of where its code lives on GitHub, the same way other Indigo plugins do. Nothing else changed.

**v1.1.4** — A line of unused code was removed. Nothing you would notice changed.

Every version is listed in the [version history](https://highsteads.github.io/MagicHome/changelog.html). The technical detail — the wire protocol, how the plugin is built, and driving it from a Python script — is in the guide's [technical notes](https://highsteads.github.io/MagicHome/technical-notes.html).

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
