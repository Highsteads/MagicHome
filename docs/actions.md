---
title: Actions and effects
nav_order: 5
---

# Actions and effects

The standard **Turn On**, **Turn Off**, **Toggle**, brightness and colour actions work on a Magic Home Light the same as on any other Indigo dimmer, and so does **Send Status Request**, which asks the controller for its state there and then.

The plugin adds nine actions of its own. To use one, add an action to a trigger, schedule or action group, and pick it from the actions listed under the plugin's own name, **MagicHome**, rather than among Indigo's device actions. Then choose the light.

Any of these actions stops an effect already running on that light.

## Set Warm White

Turns on the controller's white channel, the warm one, at the **Level** you choose from 0 to 100. It starts at 100.

## Set Cool White

Gives cool white at the **Level** you choose from 0 to 100, starting at 100. On an RGBW controller this turns red, green and blue up together, which is what the Magic Home app does. On a controller with two white channels it uses the second one. The [Your lights](devices.md) page explains why.

## Run Built-in Pattern

Runs one of the controller's own patterns at a **Speed** from 0 to 100, which starts at 50. The pattern runs on the controller, so once it has started nothing more crosses your network. The light is switched on first if it was off.

The 20 patterns are: seven colour cross fade (the one chosen to start with), red, green, blue, yellow, cyan, purple and white gradual change, red and green, red and blue, and green and blue cross fades, seven colour strobe, red, green, blue, yellow, cyan, purple and white strobe, and seven colour jumping.

## Load Custom Pattern

Sends your own list of **Colours** to the controller, which stores them and cycles through them by itself, at a **Speed** from 0 to 100 (30 to start with), with a **Transition** of **Gradual**, **Jump** or **Strobe**. The controller holds up to 16 colours, and any beyond the sixteenth are left out.

Like a built-in pattern, it needs nothing more from your network once it is running, but the timing is the controller's own and coarser than the plugin's effects.

### Writing a list of colours

Each colour is three numbers from 0 to 255, for red, green and blue, separated by commas. Colours are separated by a slash. For example, `255,140,60 / 200,60,120 / 60,90,200` is an amber, a deep pink and a soft blue. A colour the plugin cannot read is left out, and if none can be read the action does nothing and the Event Log says so.

## Fade To Colour

Fades from the colour showing now to the **Red**, **Green** and **Blue** you choose, each from 0 to 255, **Over** the number of seconds you choose. It starts at an amber of 255, 140 and 60 over 5 seconds.

**Ramp** sets how the fade moves:

| Ramp | How it looks |
|---|---|
| **Smooth — gentle at both ends** | Starts and finishes slowly. This is the one chosen to start with. |
| **Linear** | Changes at an even rate throughout. |
| **Perceptual — matches how the eye reads brightness** | Changes slowly while the light is dim and faster as it brightens, which the eye sees as even. |

If the light is off, it switches on from black and fades up.

## Start Colour Drift

Moves slowly round a **Palette** of colours, written the same way as a custom pattern, holding each colour and then crossfading to the next. **Hold each colour** sets how long it stays on each one, 120 seconds to start with, and **Crossfade over** sets how long each change takes, 20 seconds to start with. It carries on round the palette until something stops it.

Three or four colours suit a shelf.

## Start Sunrise

Brings the light up from a deep ember red, through orange, to a warm peach **Over** the number of seconds you choose — 900 seconds, which is 15 minutes, to start with. It climbs slowly at first, the way the eye sees a real sunrise, and opens up towards the end. With **Finish on warm white** ticked, which it is to start with, it ends by switching to the white channel at full.

It starts from dark, and switches the light on if it was off.

## Flash

Flashes the light in the **Red**, **Green** and **Blue** you choose, red to start with, the number of **Times** you choose, from 1 to 20. Each flash is on for under half a second and off for the same. With **Put the previous colour back afterwards** ticked, the light returns to what it showed before, its colour or, if it was showing white, its white at the same level.

## Stop Effect

Stops a plugin effect — fade, drift, sunrise or flash — and leaves the light showing whatever it had reached. It does not stop a built-in or custom pattern, which runs on the controller. Any other command to the light stops an effect too, so this is the tidy way to end one without changing anything else.

## Ideas

- **Evening lighting on a sunset trigger.** A **Fade To Colour** to 255, 120 and 40 over 120 seconds with the **Perceptual** ramp comes up so slowly that nobody sees it happen.
- **A slow drift for the evening.** A schedule at dusk runs **Start Colour Drift** with a hold of 600 seconds and a crossfade of 45, and a schedule at bedtime runs **Stop Effect** and then **Turn Off**.
- **A warning when a door is left open.** A trigger on the door runs **Flash** in red three times with **Put the previous colour back afterwards** ticked, so the light goes back to the colour it was showing.
- **A wake-up light.** A schedule half an hour before the alarm runs **Start Sunrise** over 1800 seconds.

To run any of these from an Indigo Python script, see [Driving MagicHome from a script](SCRIPTING.md) in the technical notes.
