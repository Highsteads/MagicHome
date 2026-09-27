---
title: Settings
nav_order: 6
---

# Settings

The plugin needs no account, no password and no key, so there is nothing to put in a secrets file and nothing to type in before it works.

## The plugin's settings

Open these with **Plugins → MagicHome → Configure**. They apply to every light.

| Setting | What it does |
|---|---|
| **Default poll interval (seconds)** | How often the plugin asks each controller what it is showing. It starts at 15, and must be 5 or more. |
| **Look for controllers when the plugin starts** | Ticked, the plugin searches your network as it starts and says in the log how many controllers answered. It is ticked to start with. Unticked, a light set to discovery still searches for its own controller when it starts. |
| **Re-check addresses every (minutes)** | How often the plugin searches the network again, to catch a controller your router has given a new address. It starts at 15, and must be 1 or more. A light set to discovery follows its controller to the new address. A light set to a fixed address does not. |
| **Effect smoothness (updates per second)** | How many colour changes a second the plugin's own effects send — fade, drift, sunrise and flash. It starts at 20, and can be anything from 1 to 25. Twenty looks smooth. Lower it if effects stutter, as the controller drops commands that arrive too fast. |
| **Demo this light** and **Run Demo** | Choose a light and click **Run Demo** to see it show red, green and blue one at a time, then warm white, cool white and a fade, before it goes back exactly as it was. It takes about 13 seconds. A light that was off is switched off again at the end. |
| **Debug logging** | Adds more detail to the Event Log. Only useful when chasing a problem. |

A setting left blank or holding something that is not a number falls back to its starting value rather than stopping the plugin.

## Each light's settings

Open these by double-clicking a Magic Home Light in Indigo.

| Setting | What it does |
|---|---|
| **Find the controller by** | **Discovery (recommended — survives a changed IP)** finds the controller by its MAC address, the number it was made with, so it keeps working when your router gives it a new network address. **A fixed IP address** uses the address you type in, and never moves. |
| **Controller** | With discovery, pick the controller from this list. Each one shows its name — the last six characters of its MAC address and its hardware code — and its current network address. If the list is empty, choose **Plugins → MagicHome → Discover Controllers** and open the list again. |
| **IP address** | With a fixed address, the controller's network address, such as `192.168.1.40`. Only use this if your router keeps that address for the controller, which most routers call a reserved address. |
| **"White" on this fixture means** | A choice between **Warm — the dedicated white channel** and **Cool — red, green and blue together**. At present the plugin does not act on this choice, so use the **Set Warm White** or **Set Cool White** action to pick the white you want. |
| **Check the controller every (seconds)** | Must be 5 or more. At present every light is checked at the rate set in the plugin's own **Default poll interval**, so this box makes no difference. |

The plugin sets the rest for you. When a light first answers, it reads the kind of controller, and tells Indigo which colour channels it has, so the colour picker offers what the controller can show.
