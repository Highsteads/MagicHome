---
title: The plugin menu
nav_order: 7
---

# The plugin menu

These are under **Plugins → MagicHome**.

| Menu item | What it does |
|---|---|
| **Discover Controllers** | Searches your network and lists every controller that answers in the Event Log, with its name, network address and MAC address. It also fills the **Controller** list in each light's settings. It does not move a light that is already running to a new address. The regular re-check of addresses does that, or disable the light and enable it again. If nothing answers, the log says so and reminds you the controllers must be powered on and on the same part of your network as Indigo. |
| **Run Demo** | Runs the demo on every enabled Magic Home Light. Each one shows red, green and blue one at a time, then warm white, cool white and a fade, and goes back exactly as it was, in about 13 seconds. Any command to a light stops its demo, and a demo stopped part way leaves the light on. |
| **Test Connection** | Writes the plugin's version and details of your Mac and Indigo to the Event Log, then asks every light's controller for its state and reports each one as **PASSED**, with its kind of controller, firmware version, on or off, and colour, or **FAILED**, with the reason. |
| **Show Plugin Info** | Writes the plugin's version and details of your Mac and Indigo to the Event Log, along with the default poll interval, the effect rate, how many controllers the plugin has seen and how many lights you have. |

**Test Connection** is the one to use before asking for help, as it puts everything in one block you can copy.
