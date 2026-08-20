#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    magichome_device.py
# Description: Transport for Zengge / Magic Home controllers — one connection
#              per controller, with reconnection, back-off and discovery
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.0
#
# Sockets live here; the protocol lives in magichome_protocol.py. The socket
# factory is injectable so the whole of this file can be exercised against a
# fake controller with no hardware on the bench.

import logging
import socket
import threading
import time

import magichome_protocol as proto

LOG = logging.getLogger("Plugin.magichome")

DEFAULT_TIMEOUT   = 4.0     # seconds, a single request
DRAIN_TIMEOUT     = 0.4     # seconds spent clearing unsolicited pushes
BACKOFF_START     = 5.0     # seconds before the first reconnection attempt
BACKOFF_MAX       = 300.0   # never wait longer than this between attempts
MIN_COMMAND_GAP   = 0.02    # seconds; the controller drops commands sent faster


def _default_connect(ip, port, timeout):
    return socket.create_connection((ip, port), timeout)


class Controller(object):
    """One physical controller: a socket, a lock, and its last known state.

    Every method returns rather than raises. A controller that has gone off the
    network is an ordinary condition in a house, not an exception — but it must
    never be mistaken for a controller that answered, so `available` and
    `last_error` say plainly which happened.
    """

    def __init__(self, ip, port=proto.CONTROL_PORT, mac="", model_num=None,
                 timeout=DEFAULT_TIMEOUT, connect_factory=None, name=""):
        self.ip            = ip
        self.port          = int(port) if str(port).isdigit() else proto.CONTROL_PORT
        self.mac           = proto.normalise_mac(mac)
        self.model_num     = model_num
        self.name          = name or ip
        self.timeout       = timeout
        self._connect      = connect_factory or _default_connect

        self._sock         = None
        self._lock         = threading.RLock()
        self._last_send    = 0.0

        self.available     = False
        self.last_error    = ""
        self.last_state    = None
        self.failures      = 0
        self._retry_after  = 0.0

    # -- connection ---------------------------------------------------------

    def _open(self):
        """Open the socket. Caller holds the lock."""
        self.close()
        self._sock = self._connect(self.ip, self.port, self.timeout)
        self._sock.settimeout(self.timeout)
        return self._sock

    def close(self):
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None

    def _note_failure(self, reason):
        self.failures += 1
        self.available = False
        self.last_error = str(reason)
        # Back off geometrically so a controller that has been unplugged stops
        # costing a full timeout every poll, but always keep trying — an
        # attempt that never resumes is a device that never comes back.
        wait = min(BACKOFF_START * (2 ** min(self.failures - 1, 6)), BACKOFF_MAX)
        self._retry_after = time.time() + wait
        self.close()

    def _note_success(self):
        self.failures = 0
        self.available = True
        self.last_error = ""
        self._retry_after = 0.0

    @property
    def in_backoff(self):
        return time.time() < self._retry_after

    def _drain(self):
        """Discard anything already on the socket.

        These controllers push their own state unprompted. Whatever is sitting
        in the buffer predates the request about to be made, so treating it as
        the answer produces a reading that is stale at best and noise at worst.
        """
        sock = self._sock
        if sock is None:
            return
        sock.settimeout(DRAIN_TIMEOUT)
        try:
            while True:
                if not sock.recv(4096):
                    break
        except (socket.timeout, TimeoutError):
            pass
        except OSError:
            pass
        finally:
            try:
                sock.settimeout(self.timeout)
            except OSError:
                pass

    def _pace(self):
        """Keep a minimum gap between commands. Bursts get dropped silently."""
        gap = time.time() - self._last_send
        if gap < MIN_COMMAND_GAP:
            time.sleep(MIN_COMMAND_GAP - gap)
        self._last_send = time.time()

    # -- traffic ------------------------------------------------------------

    def send(self, payload, force=False):
        """Write one already-framed message. Returns True if it went out.

        One reconnection is attempted, because the commonest failure by far is
        a socket the controller closed while idle, and that succeeds on a
        second try.
        """
        if not force and self.in_backoff:
            return False
        with self._lock:
            for attempt in (1, 2):
                try:
                    if self._sock is None:
                        self._open()
                    self._pace()
                    self._sock.sendall(bytes(payload))
                    self._note_success()
                    return True
                except (OSError, socket.timeout, TimeoutError) as err:
                    self.close()
                    if attempt == 2:
                        self._note_failure(err)
                        LOG.debug("%s: send failed — %s", self.name, err)
                        return False
        return False

    def read_state(self, force=False):
        """Query the controller and return a ControllerState, or None.

        None means "I do not know", never "it is off". A caller that treats an
        unanswered query as a reading is inventing one.
        """
        if not force and self.in_backoff:
            return None
        with self._lock:
            for attempt in (1, 2):
                try:
                    if self._sock is None:
                        self._open()
                    self._drain()
                    self._pace()
                    self._sock.sendall(proto.query())

                    buffer = b""
                    deadline = time.time() + self.timeout
                    state = None
                    while time.time() < deadline:
                        try:
                            chunk = self._sock.recv(4096)
                        except (socket.timeout, TimeoutError):
                            break
                        if not chunk:
                            break
                        buffer += chunk
                        state = proto.find_state_frame(buffer, expect_model=self.model_num)
                        if state is not None:
                            break

                    if state is None:
                        raise OSError("no valid state frame in reply")

                    if self.model_num is None:
                        self.model_num = state.model_num
                        if not proto.is_known_model(state.model_num):
                            LOG.warning("%s reports an unrecognised model byte 0x%02x — "
                                        "assuming the 8-byte RGBW message shape",
                                        self.name, state.model_num)
                    self.last_state = state
                    self._note_success()
                    return state
                except (OSError, socket.timeout, TimeoutError) as err:
                    self.close()
                    if attempt == 2:
                        self._note_failure(err)
                        LOG.debug("%s: state query failed — %s", self.name, err)
                        return None
        return None

    # -- commands -----------------------------------------------------------

    def turn_on(self):
        return self.send(proto.power(True, self.model_num or 0x06))

    def turn_off(self):
        return self.send(proto.power(False, self.model_num or 0x06))

    def set_colour(self, red, green, blue, white=None):
        model = self.model_num or 0x06
        if white is None:
            return self.send(proto.colour(red, green, blue, model_num=model,
                                          mask=proto.MASK_COLOUR))
        return self.send(proto.colour(red, green, blue, white=white,
                                      model_num=model, mask=proto.MASK_BOTH))

    def set_warm_white(self, level):
        return self.send(proto.warm_white(level, self.model_num or 0x06))

    def set_cool_white(self, level=255):
        return self.send(proto.cool_white(level, self.model_num or 0x06))

    def set_preset(self, pattern, speed=50):
        return self.send(proto.preset(pattern, speed))

    def set_custom_pattern(self, colours, speed=50, transition="gradual"):
        return self.send(proto.custom_pattern(colours, speed, transition))


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover(timeout=3.0, broadcast="255.255.255.255", socket_factory=None):
    """Broadcast for controllers and return what answers, newest reply wins.

    Discovery is by MAC, and that is the point: these controllers take a DHCP
    lease and move. An IP typed into a config dialog is correct exactly until
    the router hands out a different one.
    """
    make = socket_factory or (lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
    found = {}
    sock = None
    try:
        sock = make()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        sock.sendto(proto.DISCOVERY_PROBE, (broadcast, proto.DISCOVERY_PORT))

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                payload, _addr = sock.recvfrom(1024)
            except (socket.timeout, TimeoutError):
                break
            except OSError as err:
                LOG.debug("discovery receive failed — %s", err)
                break
            if payload == proto.DISCOVERY_PROBE:
                continue                      # our own broadcast coming back
            entry = proto.parse_discovery_reply(payload)
            if entry is not None:
                found[entry.mac] = entry
    except OSError as err:
        LOG.warning("Controller discovery failed — %s", err)
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    return sorted(found.values(), key=lambda d: d.mac)


def resolve_ip(mac, timeout=3.0, socket_factory=None):
    """Find a controller's current IP from its MAC. None if it did not answer."""
    wanted = proto.normalise_mac(mac)
    for entry in discover(timeout=timeout, socket_factory=socket_factory):
        if proto.normalise_mac(entry.mac) == wanted:
            return entry.ip
    return None
