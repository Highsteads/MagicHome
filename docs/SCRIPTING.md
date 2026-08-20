# Driving MagicHome from a script

Everything below runs in an Indigo Python script or the scripting shell. `DEV` is your Magic Home device's id.

## The standard dimmer commands

The device is a native Indigo dimmer, so nothing here is specific to this plugin.

```python
indigo.device.turnOn(DEV)
indigo.device.turnOff(DEV)
indigo.device.toggle(DEV)

indigo.dimmer.setBrightness(DEV, value=40)
indigo.dimmer.brighten(DEV, by=10)
indigo.dimmer.dim(DEV, by=10)
```

Dimming scales the current colour and keeps its hue, so a dim to 30 and back to 100 returns to exactly the colour you started on.

## Colour

Indigo works in 0-100 per channel, not 0-255.

```python
# amber
indigo.dimmer.setColorLevels(DEV, redLevel=100, greenLevel=55, blueLevel=24)

# the white channel — the warm one
indigo.dimmer.setColorLevels(DEV, redLevel=0, greenLevel=0, blueLevel=0, whiteLevel=100)
```

Remember the fixture shows colour **or** white, never both.

## Plugin actions

```python
plug = indigo.server.getPlugin("com.clives.indigoplugin.magichome")

plug.executeAction("setWarmWhite", deviceId=DEV, props={"level": "70"})
plug.executeAction("setCoolWhite", deviceId=DEV, props={"level": "100"})

# one of the controller's own patterns — runs on the controller, no further traffic
plug.executeAction("setPreset", deviceId=DEV, props={"pattern": "37", "speed": "60"})

# a smooth fade, computed by the plugin
plug.executeAction("fadeToColour", deviceId=DEV,
                   props={"red": "255", "green": "140", "blue": "60",
                          "duration": "20", "ease": "smooth"})

# wander around a palette
plug.executeAction("startDrift", deviceId=DEV,
                   props={"palette": "255,140,60 / 200,60,120 / 60,90,200",
                          "hold": "180", "fade": "25"})

# ember to daylight over fifteen minutes
plug.executeAction("startSunrise", deviceId=DEV,
                   props={"duration": "900", "finishWhite": "true"})

plug.executeAction("flashColour", deviceId=DEV,
                   props={"red": "255", "green": "0", "blue": "0",
                          "times": "3", "restore": "true"})

plug.executeAction("stopEffect", deviceId=DEV, props={})
```

**Every prop value is a string.** That is how Indigo passes them, and the plugin converts them with a guard, so a blank or a typo falls back to a default rather than taking the plugin down.

## Reading the state

```python
dev = indigo.devices[DEV]

dev.onState            # True / False
dev.brightness         # 0-100
dev.states["redLevel"] # 0-100, likewise green, blue, white

dev.states["online"]            # False when the controller is not answering
dev.states["mode"]              # "Colour", "White", "Custom pattern", "Pattern: <name>"
dev.states["effect"]            # "fade", "drift", "sunrise", "flash", or "none"
dev.states["controllerAddress"] # where it was last found
dev.states["controllerModel"]   # what the controller reports itself as
```

`online` going False means the controller stopped answering. It does **not** mean the lights are off — when nothing answers, the on/off state is left alone rather than invented.

## Worked examples

### Evening lighting on a sunset trigger

```python
plug = indigo.server.getPlugin("com.clives.indigoplugin.magichome")
plug.executeAction("fadeToColour", deviceId=DEV,
                   props={"red": "255", "green": "120", "blue": "40",
                          "duration": "120", "ease": "gamma"})
```

A two minute fade on the perceptual ramp comes up so gradually that nobody sees it happen.

### A slow drift for the evening, stopped at bedtime

```python
# at dusk
plug.executeAction("startDrift", deviceId=DEV,
                   props={"palette": "255,140,60 / 220,80,90 / 120,70,180",
                          "hold": "600", "fade": "45"})

# at bedtime — any manual command stops it, but this is the tidy way
plug.executeAction("stopEffect", deviceId=DEV, props={})
indigo.device.turnOff(DEV)
```

### Flash red if a door is left open

```python
if indigo.devices[DOOR].onState:
    plug.executeAction("flashColour", deviceId=DEV,
                       props={"red": "255", "green": "0", "blue": "0",
                              "times": "3", "restore": "true"})
```

`restore` puts back whatever colour was showing, so this can interrupt anything without leaving the room red.

### Only act when the controller is actually there

```python
dev = indigo.devices[DEV]
if not dev.states["online"]:
    indigo.server.log("Feature wall controller is not answering", isError=True)
else:
    indigo.dimmer.setBrightness(DEV, value=25)
```

## Choosing between a built-in pattern and a plugin effect

**Built-in patterns** run on the controller. Fire one and the network goes quiet, and they survive an Indigo restart. They are strobes and hard jumps, which suit a party rather than a shelf.

**Plugin effects** are computed here and streamed as colour commands. They can be as slow and smooth as you like, at the cost of a steady trickle of traffic while they run, and they stop if the plugin does.

For anything that lives in a room people sit in, the plugin effects are almost always what you want.
