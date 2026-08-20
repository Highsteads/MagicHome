# MagicHome

An Indigo plugin for Zengge WiFi LED controllers — the ones sold under **Magic Home**, **Magic Hue**, **FVTLED**, **LEDENET** and a dozen other names, and set up with the Magic Home Pro app.

It talks to them directly on your own network. No cloud account, no app running in the background, no credentials to store anywhere.

## What you get

- A native Indigo **dimmer** device, so the standard brightness slider and colour picker just work, along with everything that already understands a dimmer — control pages, triggers, schedules, HomeKit bridges, Alexa.
- **Discovery by MAC address**, so a controller keeps working when your router hands it a different IP.
- The controller's own **20 built-in patterns**, and **custom patterns** of up to 16 colours that the controller stores and cycles by itself.
- **Plugin-driven effects** the controller cannot do on its own: smooth fades, slow colour drift around a palette, and a sunrise that climbs a perceptual ramp rather than a straight line.

## What it works with

Any controller that answers on TCP 5577 — bulbs, strip controllers and the deck-light controllers sold with kits. The plugin reads the model the controller reports and adjusts what it sends.

Developed against a **FVTLED / Zengge RGBW controller** (hardware `AK001-ZJ21413`, model byte `0x06`, firmware v4). Other models are supported from a table of known types; an unrecognised one is driven with the common message shape and says so in the log rather than pretending it was recognised.

**Bluetooth-only controllers are not supported.** Some recent Zengge hardware has dropped the WiFi protocol entirely — if the Magic Home app finds your lights over Bluetooth rather than the network, this plugin cannot reach them.

## A word about white

An RGBW controller has **one** white channel, and it is the warm one. What the app offers as "cool white" is red, green and blue driven together — there is no second white channel to address. The plugin does the same thing, and gives you both as separate actions so you can pick.

The two are mutually exclusive on this hardware: the fixture shows its colour channels or its white one, never both. Asking for both applies whichever you evidently wanted, and says so once in the log.

## Installing

1. Go to the [Releases page](https://github.com/Highsteads/MagicHome/releases) and download `MagicHome.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `MagicHome.indigoPlugin`
3. Double-click `MagicHome.indigoPlugin` — Indigo will install it automatically

## Setting up a light

1. **Plugins -> MagicHome -> Discover Controllers.** Every controller on your network answers with its address, and they are listed in the Indigo log.
2. **New Device -> MagicHome -> Magic Home Light.**
3. Leave the finding method on **Discovery** and pick your controller from the list. It is named by the last six characters of its MAC address, the same way the Magic Home app names it.
4. Save. The device fills in straight away.
5. Optional, but worth it: **Plugins → MagicHome → Configure**, pick the light and press **Run Demo**. It runs through the three colour channels one at a time, both whites and a fade, then puts the light back exactly as it was — about fifteen seconds. Showing the channels separately is how you spot a strip wired in a different order, and showing both whites is how the warm/cool business stops being a surprise.

The controller must be on the same subnet as your Indigo server for discovery to find it. If you would rather pin an address, switch to **A fixed IP address** — but give the controller a DHCP reservation on your router first, or the device will stop working the day its lease changes.

## Actions

| Action | What it does |
|---|---|
| Set Warm White | Drives the dedicated white channel |
| Set Cool White | Drives red, green and blue together, as the app does |
| Run Built-in Pattern | One of the controller's own 20 patterns, at a speed you choose |
| Load Custom Pattern | Up to 16 colours, stored in the controller and cycled by it |
| Fade To Colour | A smooth fade over as long as you like |
| Start Colour Drift | Wanders around a palette, holding each colour and crossfading |
| Start Sunrise | Ember to daylight over minutes, on a perceptual ramp |
| Flash | A short attention-getter that puts the previous colour back |
| Stop Effect | Stops a plugin-driven effect and leaves the lights be |

Palettes are written as `R,G,B` triples separated by a slash — `255,140,60 / 200,60,120 / 60,90,200`.

### Built-in patterns against plugin effects

The **built-in patterns** run on the controller. Fire one and the network goes quiet — nothing further crosses it, and they carry on through an Indigo restart. They are also strobes and hard jumps, which suit a party rather than a shelf.

The **plugin effects** are computed here and streamed as ordinary colour commands. They can be as slow and as smooth as you want — a twenty-second crossfade, a fifteen-minute sunrise — at the cost of a steady trickle of traffic while they run, and they stop if the plugin does.

Any manual command stops a running effect, so grabbing the brightness slider always wins.

## Settings

| Setting | Default | Notes |
|---|---|---|
| Poll interval | 15s | How often each controller is asked what it is doing |
| Look for controllers at startup | on | |
| Re-check addresses | 15 min | Finds a controller its DHCP lease has moved |
| Effect smoothness | 20/sec | Measured ceiling is about 40; above 25 commands start being dropped |
| Debug logging | off | |

The Configure dialog also carries a **Run Demo** button, and there is a **Run Demo** item in the plugin's menu that demos every light you have.

## How it talks to the controller

Worth knowing if you are ever debugging it.

- **TCP 5577** carries commands and state. There is no authentication of any kind, so anything on your network can drive the lights. That is an argument for keeping these controllers on an IoT VLAN.
- **UDP 48899** is discovery. A broadcast of `HF-A11ASSISTHREAD` makes every controller answer with its IP, MAC and hardware id.
- Messages are a few bytes with a plain sum as a checksum. **A message of the wrong length is not rejected — it is read as a different command.** The 9-byte form sent to an 8-byte controller switched a live unit off. The plugin keeps a table of which models take which.
- Controllers **push their own state unprompted**, wrapped in a `b0 b1 b2 b3` header. One reply per request is not a safe assumption, so every state read scans for a frame and checks its checksum rather than trusting what arrives.
- Sending a colour to a controller that is off **turns it on**.

## Documentation

| | |
|---|---|
| [Protocol reference](docs/PROTOCOL.md) | The wire protocol, measured against real hardware — framing, commands, state, discovery, model table, and the several places where the published accounts and the controller disagree |
| [Architecture](docs/ARCHITECTURE.md) | How the plugin is built and why, including the timer-slack problem that shapes the effects engine |
| [Scripting](docs/SCRIPTING.md) | Driving it from Indigo Python, with worked examples |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | When it does not do what you expected |

## Troubleshooting in brief

**Discovery finds nothing.** The controller must be on the same subnet as the Indigo server — a broadcast does not cross a router. Run the sweep again before concluding anything; UDP broadcast on wifi is genuinely lossy.

**The device says offline.** Compare its address state against what Discover Controllers reports. A device set to discovery heals itself within a minute or two; one pinned to a fixed IP that has moved will not.

**Colours are wrong.** Strip controllers can be wired in any channel order — a strip wired GRB shows red where you asked for green. That is the wiring, and the Magic Home app has a setting for it.

**An effect stutters.** Lower the effect smoothness. Commands sent faster than the controller accepts are dropped rather than queued.

The [full troubleshooting guide](docs/TROUBLESHOOTING.md) covers the rest.

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
