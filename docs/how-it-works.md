---
title: How it works
nav_order: 4
---

# How it works

You do not need to know any of this to use the plugin. It is here for anyone who likes to know what is going on.

## Talking to the controller

Indigo talks to each controller directly over your home network, on the controller's port 5577, with no account and no internet involved. The controller has no password of any kind, so anything on your network can switch these lights, which is a reason some people keep smart devices on a separate network of their own.

Every so often — every 15 seconds to start with — the plugin asks each controller what it is showing, and brings Indigo up to date. It asks again straight after every command, so Indigo shows the result of what you did within a second or two.

If a controller does not answer, the plugin tries once more at once, because the commonest failure is a controller that has quietly closed an idle connection. If that fails too, the light is marked offline, and the plugin waits a little longer before each new try — five seconds, then ten, then twenty, and so on up to five minutes. It never stops trying, so a controller that comes back is found again within about five minutes at most. A command to a light that is offline and waiting between tries is not sent, and the Event Log says the send failed.

## Finding each controller

Your router hands out network addresses, and now and then it gives a controller a different one. So rather than trusting an address, the plugin knows each controller by its **MAC address** — a number every network device is made with, a bit like a serial number.

To find them, the plugin calls out across your network four times over four seconds, and every controller answers with its address, its MAC address and its hardware code. Controllers can miss a call on wifi, which is why it calls four times. What it hears is added to what it already knows, and never replaces it, so one missed answer cannot lose a controller the plugin had already found.

- **When the plugin starts,** it searches once and says in the log how many controllers answered, unless you have switched that off in its settings.
- **Every 15 minutes** to start with, it searches again. If a light set to discovery has moved, the plugin points it at the new address and the log says where it moved from and to.
- **A light that has not been found yet** keeps looking by itself, at most once a minute, until its controller answers.
- **A light set to a fixed address** is never moved. If its address changes, it stays offline until you correct it.

That call across the network does not pass through a router, so a controller on a separate network is not found. A light set to a fixed address can still reach it, if your router lets the two networks talk.

## Built-in patterns and the plugin's own effects

The **built-in patterns** and your own **custom pattern** run on the controller itself. The plugin sends one command, and after that nothing more crosses your network. They carry on if Indigo or the plugin stops. The built-in ones are mostly strobes and quick changes, which suit a party better than a shelf.

The plugin's own **effects** — fade, drift, sunrise and flash — are worked out by the plugin and sent to the controller as a stream of ordinary colour commands, 20 a second to start with. That means they can be as slow and smooth as you like, such as a twenty-second crossfade or a fifteen-minute sunrise, but they need the plugin running, and they stop if it stops.

- **Each light runs one effect at a time.** Starting a second stops the first.
- **Any command to the light stops an effect,** whether it comes from you, a trigger, a schedule or a control page.
- **An effect keeps to its time.** If Indigo is busy and a step is late, the plugin skips it rather than showing it late, so a fade may look a little coarser but finishes on time. The last step is never skipped, so the light always ends on the colour you asked for.
- **An effect gives up after five failed commands in a row** and says so in the log, as that means the controller has stopped answering.

The controller accepts roughly 40 commands a second before it starts dropping them, which is why the plugin's setting stops at 25.

## What goes in the log

The Event Log has Indigo's own line when the plugin starts, one line saying how many controllers the plugin found, and one line for each command it sends, such as `sent "Shelf Lights" on`. It also has a warning when a light stops answering and a note when it comes back, when it moves to a new address, and when an effect gives up. Turn on **Debug logging** in the plugin's settings for more detail while chasing a problem.
