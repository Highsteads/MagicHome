# The Zengge / Magic Home wire protocol

Everything here was measured against a live controller and checked by reading the state back. Where a published library and the hardware disagreed, the hardware won and the disagreement is noted.

Reference controller: **FVTLED / Zengge RGBW**, hardware `AK001-ZJ21413`, model byte `0x06`, firmware v4.

## Ports

| Port | Protocol | Purpose |
|---|---|---|
| 5577 | TCP | Commands and state. No authentication of any kind. |
| 48899 | UDP | Discovery, and the controller's wifi setup. |
| 80 | TCP | A web configuration page on some firmware. Refused on v4. |

Anything that can reach port 5577 can drive the lights. There is no password, no token and no rate limit. Treat these controllers as untrusted devices and put them somewhere you are happy for that to be true.

## Framing

A message is a few plain bytes with a **one-byte checksum appended**, which is the sum of every preceding byte, taken modulo 256.

```python
def frame(payload):
    return bytes(payload) + bytes([sum(payload) & 0xFF])
```

Legacy model `0x01` is the exception: it uses a different, checksum-free encoding.

### Message length is per model, and getting it wrong is silent

There are two colour message shapes:

```
8-byte:  31 R G B W <mask> 0f <checksum>          RGB and RGBW controllers
9-byte:  31 R G B W W2 <mask> 0f <checksum>       RGBWW and RGBCW controllers
```

**A message of the wrong length is not rejected. It is read as a different command.** Sending the 9-byte form to an 8-byte controller switched a live unit off — no error, no complaint, just a different outcome from the one asked for. Keep a table of which model takes which, and never guess.

## Commands

| What | Bytes (before the checksum) |
|---|---|
| On | `71 23 0f` |
| Off | `71 24 0f` |
| Colour | `31 R G B W f0 0f` |
| White | `31 00 00 00 W 0f 0f` |
| Both channels | `31 R G B W 00 0f` — see below |
| Built-in pattern | `61 <pattern> <delay> 0f` |
| Custom pattern | `51 …` — see below |
| Read state | `81 8a 8b 96` (already checksummed) |

### The write mask

Byte 6 of an 8-byte colour message decides which half of the fixture it applies to: `f0` colour only, `0f` white only, `00` both.

**`00` is not honoured by every model.** On a model `0x06` the message is accepted, the controller reports success, and the white channel does not move. That is the worst available failure — a command that looks like it worked. Record per model whether both channels can be driven at once, and where they cannot, apply the one that was actually wanted rather than half-doing the job quietly.

### Cool white is not a white channel

An RGBW controller has **one** white channel, and it is the warm one. What the Magic Home app presents as "cool white" is **red, green and blue driven together at equal level**:

```
cool white  =  31 ff ff ff 00 f0 0f
warm white  =  31 00 00 00 ff 0f 0f
```

Confirmed by setting cool white in the app and reading the frame straight back: `R=255 G=255 B=255`, white channel `0`. There is no second white channel to address on this model. An RGBWW model has one, and it belongs in the `W2` byte of the 9-byte form.

The two are mutually exclusive: the fixture shows its colour channels **or** its white one.

### Sending a colour turns the controller on

Measured: with the controller off, a colour message brings it on by itself. An explicit on beforehand is harmless and worth keeping for models that behave otherwise.

### Speed

Built-in patterns take a **delay** byte from 1 (fastest) to 31 (slowest), converted from a 0-100 speed:

```python
delay = int(((100 - speed) * 30) / 100) + 1
```

### Custom patterns

Up to 16 colours, stored in the controller and cycled by it with no further traffic.

```
51 R G B   00 R G B   00 R G B   …   00 <delay> <transition> ff 0f <checksum>
```

The first colour carries the `0x51` lead byte and the rest carry `0x00`. Unused slots are padded with the `(1, 2, 3)` sentinel the firmware expects — padding with black shows as a blackout in the sequence. Transition is `3a` gradual, `3b` jump, `3c` strobe.

## Reading state

`81 8a 8b 96` returns fourteen bytes.

| Byte | Meaning |
|---|---|
| 0 | Always `0x81` |
| 1 | Model number |
| 2 | Power — `0x23` on, `0x24` off |
| 3 | Mode — `0x61` static colour, `0x60` custom pattern, `0x25`–`0x38` a built-in pattern |
| 5 | Pattern speed — **see below** |
| 6, 7, 8 | Red, green, blue |
| 9 | White |
| 10 | Firmware version |
| 11 | Second white |
| 12 | Write mode — `f0` colour, `0f` white |
| 13 | Checksum of bytes 0-12 |

### Byte 5 is not the raw delay

Widely documented as the delay byte. On this firmware it is not — it reports **`100 - 3 × delay`**. Asking for speeds of 90, 50 and 10 read back as 88, 52 and 16, which invert to exactly 90, 50 and 10. Three times out of three.

The two encodings overlap between 7 and 31, so a byte in that range is genuinely ambiguous and no amount of care resolves it from the byte alone. Only one firmware has been measured, so decode with the measured form and fall back to a raw delay only when the result could not be a valid delay.

Speed is meaningless outside pattern mode. Report nothing there rather than a number — a number that means nothing reads as a measurement.

### The controller talks when it was not asked

These controllers **push their own state unprompted**, wrapped in a header beginning `b0 b1 b2 b3` and carrying a sequence number. One reply per request is not a safe assumption.

This matters more than it sounds. A misaligned read produces fourteen bytes that parse perfectly and mean nothing, so the failure is not an error — it is a plausible wrong answer. During development it produced a full page of readings, every one of them noise, with nothing to suggest anything was wrong.

Scan the buffer for a frame, verify its checksum, prefer the newest match, and once the model byte is known, ignore frames that disagree with it.

### Only one conversation at a time

The controller accepts a single TCP connection. A second one opened while the first is live does not work, and it fails by refusing commands rather than by refusing to connect.

## Discovery

Broadcast the ASCII string `HF-A11ASSISTHREAD` to UDP 48899. Each controller replies with:

```
<ip>,<mac>,<hardware id>,<uuid>
```

for example `192.168.1.50,806A34112233,AK001-ZJ21413,…`. The name the Magic Home app shows is the **last six characters of the MAC** — not a model number, however much it looks like one.

### One probe is not enough

UDP broadcast on wifi is sent at the lowest rate with no acknowledgement and no retry, so losing a frame is ordinary rather than exceptional. Measured on a live network: a **single** probe found the controller roughly half the time. **Four** probes spread across the listening window found it six sweeps out of six, and five out of five again later.

Two things follow, and both are easy to get wrong:

- **Keep listening after a timeout.** Giving up on the first quiet gap also loses a slow controller.
- **Merge the result into whatever you already knew. Never replace it.** An empty sweep means "nothing answered this time", not "there is nothing there". Replacing a cache with an empty sweep turns one lost frame into a houseful of devices with no address.

Some firmware replies to the discovery port rather than to the port the probe came from, so bind 48899 where you can and carry on unbound where you cannot.

## Model numbers

Byte 1 of the state frame.

| Model | Description | Channels | Message |
|---|---|---|---|
| `0x01` | Legacy controller | RGB | pre-checksum encoding |
| `0x04` | Controller RGBW | RGBW | 8-byte, honours both channels |
| `0x06` | Controller RGBW | RGBW | 8-byte, colour **or** white |
| `0x07` | Controller RGBCW | RGBWW | 9-byte |
| `0x21` | Dimmable white bulb | W | 8-byte |
| `0x25` | Controller RGBWW | RGBWW | 9-byte |
| `0x27` | Warm white controller | W | 9-byte |
| `0x33` | Controller RGB | RGB | 8-byte |
| `0x35` | Bulb RGBWW | RGBWW | 9-byte |
| `0x44` | Bulb RGBW | RGBW | 8-byte |
| `0x81` | Controller RGBW | RGBW | 8-byte, honours both channels |

An unrecognised model is driven with the 8-byte shape, which is the commonest and the safer guess — and it is logged as unrecognised rather than quietly treated as understood.

## Built-in patterns

Contiguous, `0x25` to `0x38`.

| Code | Pattern | Code | Pattern |
|---|---|---|---|
| `0x25` | Seven colour cross fade | `0x2F` | Green/blue cross fade |
| `0x26` | Red gradual change | `0x30` | Seven colour strobe |
| `0x27` | Green gradual change | `0x31` | Red strobe |
| `0x28` | Blue gradual change | `0x32` | Green strobe |
| `0x29` | Yellow gradual change | `0x33` | Blue strobe |
| `0x2A` | Cyan gradual change | `0x34` | Yellow strobe |
| `0x2B` | Purple gradual change | `0x35` | Cyan strobe |
| `0x2C` | White gradual change | `0x36` | Purple strobe |
| `0x2D` | Red/green cross fade | `0x37` | White strobe |
| `0x2E` | Red/blue cross fade | `0x38` | Seven colour jumping |

## Throughput

The reference controller accepted about **40 commands a second** sustained. Beyond that, commands are dropped rather than queued, which shows as stutter in a fade. Twenty updates a second is smooth and leaves room to spare.

## What the app does that the controller does not

Music and camera modes are the **phone** doing the work. It samples its own microphone or camera, works out a colour, and streams ordinary colour commands. There is no sound or vision anywhere in the protocol, and nothing in the state frame reports either. Anything that can send colours quickly can do the same thing, given a microphone of its own.
