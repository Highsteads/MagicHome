---
title: When something goes wrong
nav_order: 8
---

# When something goes wrong

Each section starts with what you see, then what it means and what to do.

## Discover Controllers finds nothing

The plugin called out across your network and no controller answered.

- **Run it again before concluding anything.** Wifi loses the odd call, and although the plugin calls four times each search, a busy network can still swallow the lot.
- **Check the controller has power** and that the Magic Home app can see it.
- **Check it is on the same part of your network as the Mac that runs Indigo.** The plugin's call does not pass through a router, so a controller on a separate network for smart devices is not found. Give it a reserved address on your router and set the light to **A fixed IP address** instead.
- **Do the Bluetooth check.** Turn Bluetooth off on your phone, stay on your home wifi, and open the Magic Home app. If the app cannot find the lights, they are Bluetooth-only, and no Indigo plugin can reach them. There is no setting to change and no way round it.

## A light shows "offline"

The controller has stopped answering. The light's **Online** state is off, but its on and off state is left alone, so it does not mean the lights are off.

- Compare the light's **IP Address** state with what **Plugins → MagicHome → Discover Controllers** reports.
- **A light set to discovery** follows its controller to a new address at the next re-check of addresses, every 15 minutes to start with. To catch it sooner, run **Discover Controllers**, then disable the light in Indigo and enable it again, and it picks up the new address as it starts.
- **A light set to a fixed address** stays offline until you correct the address in its settings or switch it to discovery. A reserved address on your router stops this happening.
- If the controller has lost power, the red clears by itself within about five minutes of it coming back.

## A light shows "no address"

The light is set to discovery and its controller has not answered yet. The plugin keeps looking, about once a minute, or less often if the light is set to be checked less often than that. Check the controller has power, and run **Discover Controllers**.

## The colours are wrong

**Red shows as green, or similar.** Run the demo — **Plugins → MagicHome → Run Demo**, or **Run Demo** in the Configure dialog for one light. It shows red, green and blue one at a time, so a strip wired in a different order shows up within a few seconds. A strip can be wired in any order, and the Magic Home app has a setting for it, which is the place to put it right.

**Cool white looks slightly coloured.** On an RGBW controller cool white is red, green and blue turned up together, as the app does it. If it looks tinted, the strip's three colours are not perfectly matched.

**White and colour together only gives one of them.** Most RGBW controllers show their colour channels or their white channel, never both. If you ask for any colour, you get the colour, and the Event Log says so the first time it happens on each light.

## Changing the colour does nothing, but on and off still work

**Close the colour picker and open it again.**

If the plugin has been restarted — by you, by an upgrade, or by Indigo — a colour picker that was already open no longer reaches the plugin. Dragging it does nothing, and nothing appears in the log. On and off keep working, because they come from the device list, which stays live. This happens with any Indigo plugin, most often while you are setting one up.

## An effect stutters

Lower **Effect smoothness** in **Plugins → MagicHome → Configure**. The controller drops commands that arrive faster than it can take them, and each dropped one shows as a jump.

A busy Indigo server can also make a fade look a little coarser, because the plugin skips a late step rather than letting the effect run long. It still finishes on time and on the right colour.

## An effect stopped by itself

- Any command to the light stops an effect, including one from a trigger, a schedule or a control page.
- An effect also gives up after five failed commands in a row, and the log says so. That means the controller stopped answering part way through. Check its **Online** state.
- A plugin effect stops if the plugin stops or restarts. A built-in or custom pattern carries on, because it runs on the controller.

## The log says a controller is an unrecognised model

The plugin does not know that kind of controller, so it treats it as an RGBW controller, the commonest kind. If the light behaves oddly, please raise an issue with the **Test Connection** output, so I can add it.

## The log says "no handler for device action"

Indigo asked the light to do something the plugin does not handle, so nothing was sent. Please raise an issue saying what you were doing at the time.

## Still stuck?

Choose **Plugins → MagicHome → Test Connection**, copy the lines it writes to the Event Log, and post them on the [Indigo forum](https://forums.indigodomo.com) with a description of what you see. You can also [raise an issue on GitHub](https://github.com/Highsteads/MagicHome/issues). Turning on **Debug logging** in the plugin's settings adds more detail to what you send.
