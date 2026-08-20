# Troubleshooting

## Discovery finds nothing

**The controller must be on the same subnet as the Indigo server.** Discovery is a UDP broadcast, and broadcasts do not cross a router. A controller on a separate IoT VLAN will not be found unless you have deliberately arranged a broadcast route.

**Run it again before concluding anything.** UDP broadcast on wifi goes out at the lowest rate with no acknowledgement and no retry, so losing a frame is ordinary. The plugin probes four times per sweep for exactly this reason, but a genuinely busy network can still swallow all four.

**Check it is powered and joined.** If the Magic Home app cannot see it either, the problem is not the plugin.

**Bluetooth-only controllers cannot be found at all**, because they are not on the network to be found. Some recent Zengge hardware — the `LEDnetWF` family and various BL602-based controllers — dropped the wifi protocol entirely.

To settle which kind you have: **turn Bluetooth off on your phone, stay on your home wifi, and open the Magic Home app.** If the lights still work, it is a wifi controller and the problem is elsewhere on this page. If the app cannot find them, it is Bluetooth-only and nothing here will help — there is no setting to change and no workaround.

## The device says offline

Compare the device's `controllerAddress` state against what **Discover Controllers** reports.

- **Set to discovery:** the plugin re-checks addresses on a timer and hunts for a missing controller once a minute, so this should heal itself within a minute or two. If it does not, the controller is not answering at all.
- **Pinned to a fixed IP:** it will sit offline until you correct the address or switch it to discovery. This is the failure a DHCP reservation prevents.

`online` going False means the controller stopped answering. It does not mean the lights are off — the plugin leaves the on/off state alone rather than inventing one.

## The colours are wrong

**Red shows as green, or similar.** Run the demo first — **Plugins → MagicHome → Configure → Run Demo**, or the **Run Demo** item in the plugin's menu. It shows red, green and blue one at a time, so a strip wired in a different channel order gives itself away in the first five seconds.

Strip controllers can be wired in any order, and a strip wired GRB shows red where you asked for green. That is the wiring rather than the plugin — the Magic Home app has a setting for it, and that is where to fix it.

**Cool white looks like colour rather than white.** It is. An RGBW controller has one white channel and it is the warm one — the app's cool white is red, green and blue together, and this plugin does the same thing. If the result looks tinted, the strip's channels are not perfectly balanced, which is a property of the strip.

**Asking for colour and white together only applies one of them.** On most RGBW controllers the fixture shows colour or white, never both. The plugin applies whichever you evidently wanted and says so once in the log.

## An effect stutters

Lower **Effect smoothness** in the plugin settings. Commands sent faster than the controller accepts are dropped rather than queued, and the dropped ones show as a jump.

A busy Indigo server can also cost an effect frames — by design, since the alternative is the effect running long. A fade that looks slightly coarse but finishes on time is the intended behaviour.

## An effect stopped by itself

An effect gives up after five refused commands, and says so in the log. That means the controller stopped answering part way through. Check `online`.

An effect also stops the moment any manual command arrives, including one from a trigger, a schedule or a control page. That is deliberate — grabbing the brightness slider should always win.

## The plugin will not start

Check the Indigo log for the line after `Starting plugin "MagicHome"`. A healthy start produces one line saying how many controllers were found.

If a setting has been left blank, the plugin falls back to a default rather than failing, so a blank field is not the cause.

## Nothing in the log at all

Turn on **Debug logging** in the plugin settings. Normal operation is deliberately quiet: Indigo's own start line, one line at startup, and a line per command.

## Checking a controller quickly

**Run Demo** puts a light through the three colour channels one at a time, both whites and a fade, then restores it exactly as it was. About fifteen seconds. It is the fastest way to answer "is this wired the way I think, and can Indigo actually reach it".

It stops the moment any command arrives for that light, so you can cut it short by touching the brightness slider. If it is stopped part way it leaves the light on, rather than guessing that you wanted it off.

## Getting help

**Plugins → MagicHome → Show Plugin Info** dumps the full environment. **Test Connection** dumps the same thing and then reports what every device's controller actually said. Paste that whole block into a bug report — it is one place with the version, the environment and the result together.
