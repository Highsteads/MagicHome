# How the plugin is put together

Four files, in layers, with no upward dependencies. The point of the split is that most of the plugin can be tested without a controller, without Indigo, and without a network.

```
plugin.py               Indigo — devices, actions, the worker loop
   |
magichome_effects.py    fades, drift, sunrise, flash
   |
magichome_device.py     sockets, reconnection, discovery
   |
magichome_protocol.py   bytes
```

## `magichome_protocol.py`

Pure functions over bytes. No sockets, no Indigo, no clock. Given a colour it returns the message to send; given fourteen bytes it returns a decoded state or `None`.

Every fact in it was measured — see [PROTOCOL.md](PROTOCOL.md). It carries the model table, and the model table is the reason it exists as a separate layer: which message shape a controller takes, and whether it can drive colour and white at once, are facts about the hardware, not decisions the transport should be making.

`parse_state` returns `None` for anything that fails its checksum. `find_state_frame` scans a buffer rather than trusting the first fourteen bytes to be an answer, because these controllers push state nobody asked for.

## `magichome_device.py`

One `Controller` per physical box: a socket, a lock, and the last state it reported.

**Every method returns rather than raises.** A controller that has gone off the network is an ordinary condition in a house, not an exceptional one. But it must never be mistaken for one that answered, so `available` and `last_error` say plainly which happened, and a failed state query returns `None` — which means "I do not know", never "it is off".

The socket factory is injectable, which is what makes the whole layer testable against a fake controller that answers with a captured frame, pushes state unprompted, and dies mid-conversation.

Failures back off geometrically to a five-minute ceiling, so an unplugged controller stops costing a full timeout on every poll — but it never stops retrying. A retry that gives up permanently is a device that never comes back.

## `magichome_effects.py`

The plan is separated from the running of it. Every `plan_*` function is pure and returns a list (or a generator, for a drift that has no end) of steps. The maths is testable with no clock, no thread and no socket.

### The runner is driven by the clock, not by the step count

This is the part worth reading if you are writing anything similar.

A short sleep is not short. Measured inside the Indigo plugin host, `threading.Event.wait(0.05)` returns after a **median of 100 ms** — asked 50, got 100, worst 125. macOS gives a sleeping thread generous timer slack and no amount of arithmetic persuades it to wake sooner.

Walking a plan one step per sleep therefore cannot keep time, and the error is proportional: a twenty second fade took 23.2 seconds. Subtracting elapsed time from the next wait does not fix it, because the floor is the slack itself.

So the runner tracks when each step is **due** against a start time, and **drops** a frame whose moment has already passed rather than showing it late. A busy machine then costs frames instead of time, which is the right way round — a slightly coarser fade looks the same, whereas a sunrise finishing three minutes after dawn does not. Twenty seconds asked now takes 20.1.

The last frame is never dropped. Landing a frame short leaves the lights on a colour nobody asked for, and the next state poll reports that as the truth.

### One effect at a time

Starting a second effect stops the first. Two threads fighting over one set of lights reads as flicker and is very hard to explain afterwards. Any manual command stops a running effect too, so grabbing the brightness slider always wins.

An effect gives up after five refused commands. A controller that has left the network will not come back inside one effect, and hammering it for the next hour helps nobody.

## `plugin.py`

The device is a native Indigo `dimmer` with `SupportsColor`, `SupportsRGB` and `SupportsWhite`. The colour channel states are **native** and deliberately not declared in `Devices.xml` — Indigo builds them from those properties, and declaring them over the top is rejected.

### Things that are easy to get wrong here

**Indigo re-serialises every ConfigUI field as a string once a dialog has been saved**, including menu options that look like numbers. Nothing arriving from a dialog is used as a number without a guarded conversion. An unguarded `int("")` in `deviceStartComm` takes the plugin down with it, and it hides until somebody opens and saves a dialog they had never opened before.

**The whole worker tick is wrapped, and each device again inside that.** One controller throwing must not silently end all polling for every other one.

**State is written only after a send actually succeeded.** Reporting success from the absence of an exception is how a plugin comes to log a confident no-op.

**An unanswered query is published as unknown, not as off.** Recording it as off would invent a reading nobody took, and a dead controller would look like a light somebody had switched off.

### Addressing

A device is addressed by **MAC**, resolved to an IP through discovery. These controllers take a DHCP lease and move; an IP typed into a dialog is correct exactly until the router says otherwise.

Two consequences that were both live bugs before they were fixed:

- **An empty sweep merges into the cache rather than replacing it.** UDP broadcast is lossy, so a sweep can come back empty while every controller is sitting there perfectly happy.
- **A device that has never been placed keeps looking**, rate limited to one sweep a minute. "Configured but never found" is not a terminal state. One unlucky sweep at startup used to leave a light dead until the next re-check fifteen minutes later.

### Reporting during an effect

While an effect runs the plugin knows exactly what it is showing, so it says so rather than leaving the device stale until the next poll. Writes are throttled to one a second — a fade sends twenty steps a second, and twenty state writes a second is a number nobody can read that fast.

The **final** frame is published immediately, throttle or no throttle. Without that the device sits showing a colour from part way through the fade until the next poll corrects it: a reading that is wrong rather than merely old.

## Tests

187 of them, in four files. `tests/indigo_stub.py` provides just enough of the `indigo` module that the **shipped** `plugin.py` can be imported and its real methods called — a re-implementation in the test file would only ever test the re-implementation.

Every protocol fixture is a byte string captured from a real controller, not one composed to match the parser. A fixture built from an assumption tests the assumption, and green tests over a wrong fixture are the most convincing available way to be wrong.

That is not a claim that the tests are sufficient. When this plugin was first pointed at real hardware it had 165 green tests, and the hardware immediately found seven bugs — in every case because the fixture and the code shared the same wrong assumption. Two of them would have read as "the plugin randomly stops working". The tests stop regressions; they do not establish that it works.
