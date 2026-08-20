#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_device.py
# Description: Contract tests for the Magic Home transport layer
# Author:      CliveS & Claude Opus 5
# Date:        20-08-2026 21:55
# Version:     1.0
#
# A fake controller stands in for the hardware. It behaves like the real one in
# the ways that matter: it answers a query with a real captured frame, it can
# push state nobody asked for, and it can die mid-conversation.

import os
import socket
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "MagicHome.indigoPlugin", "Contents", "Server Plugin"))

import magichome_protocol as proto      # noqa: E402
import magichome_device as mdev         # noqa: E402


def hexb(text):
    return bytes.fromhex(text.replace(" ", ""))


REAL_RED  = hexb("81 06 23 61 12 50 ff 00 00 00 04 00 f0 60")
REAL_PUSH = hexb("b0 b1 b2 b3 00 02 02 4b 00 14 ea 81 01 00 06 04 23 61 01 50 "
                 "f0 40 64 08 00 00 02 00 00 00 12")


class FakeSocket(object):
    """Stands in for a connected controller."""

    def __init__(self, reply=REAL_RED, pushes=b"", fail_on_send=False,
                 fail_after=None, reply_junk=False):
        self.sent          = []
        self.closed        = False
        self._reply        = reply
        self._pushes       = pushes
        self._pending      = bytearray(pushes)
        self._fail_on_send = fail_on_send
        self._fail_after   = fail_after
        self._reply_junk   = reply_junk
        self.timeout       = None

    def settimeout(self, value):
        self.timeout = value

    def sendall(self, payload):
        if self.closed:
            raise OSError("socket is closed")
        if self._fail_on_send:
            raise OSError("connection reset by peer")
        if self._fail_after is not None and len(self.sent) >= self._fail_after:
            raise OSError("connection reset by peer")
        self.sent.append(bytes(payload))
        if bytes(payload) == proto.query():
            self._pending.extend(hexb("00 11 22") if self._reply_junk else self._reply)

    def recv(self, size):
        if self.closed:
            raise OSError("socket is closed")
        if not self._pending:
            raise socket.timeout("timed out")
        chunk = bytes(self._pending[:size])
        del self._pending[:size]
        return chunk

    def close(self):
        self.closed = True


class FakeUdpSocket(object):
    def __init__(self, replies, raise_on_send=None):
        self._replies      = list(replies)
        self._raise_on_send = raise_on_send
        self.sent          = []
        self.closed        = False
        self.options       = []

    def setsockopt(self, level, name, value):
        self.options.append((level, name, value))

    def settimeout(self, value):
        pass

    def sendto(self, payload, addr):
        if self._raise_on_send:
            raise self._raise_on_send
        self.sent.append((bytes(payload), addr))

    def recvfrom(self, size):
        if not self._replies:
            raise socket.timeout("timed out")
        return self._replies.pop(0), ("192.168.1.1", proto.DISCOVERY_PORT)

    def close(self):
        self.closed = True


def controller(sockets, **kwargs):
    """Build a Controller whose connections come from a scripted list."""
    made = list(sockets)

    def factory(ip, port, timeout):
        if not made:
            raise OSError("no route to host")
        nxt = made.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    ctrl = mdev.Controller("192.168.1.50", model_num=0x06,
                           connect_factory=factory, timeout=0.3, **kwargs)
    return ctrl


class TestSending(unittest.TestCase):

    def test_a_command_reaches_the_socket(self):
        sock = FakeSocket()
        ctrl = controller([sock])
        self.assertTrue(ctrl.turn_on())
        self.assertEqual(sock.sent[-1], hexb("71 23 0f a3"))

    def test_off_sends_the_bytes_that_worked_live(self):
        sock = FakeSocket()
        ctrl = controller([sock])
        ctrl.turn_off()
        self.assertEqual(sock.sent[-1], hexb("71 24 0f a4"))

    def test_a_dropped_socket_is_reconnected_once(self):
        dead, good = FakeSocket(fail_on_send=True), FakeSocket()
        ctrl = controller([dead, good])
        self.assertTrue(ctrl.turn_on())
        self.assertTrue(ctrl.available)
        self.assertEqual(good.sent[-1], hexb("71 23 0f a3"))

    def test_two_failures_mark_it_unavailable_rather_than_pretending(self):
        ctrl = controller([FakeSocket(fail_on_send=True), FakeSocket(fail_on_send=True)])
        self.assertFalse(ctrl.turn_on())
        self.assertFalse(ctrl.available)
        self.assertTrue(ctrl.last_error)

    def test_an_unreachable_controller_does_not_raise(self):
        ctrl = controller([])
        self.assertFalse(ctrl.turn_on())
        self.assertFalse(ctrl.available)

    def test_colour_with_white_uses_the_both_channels_mask(self):
        sock = FakeSocket()
        ctrl = controller([sock])
        ctrl.set_colour(10, 20, 30, white=40)
        self.assertEqual(sock.sent[-1][5], proto.MASK_BOTH)

    def test_colour_without_white_leaves_the_white_channel_alone(self):
        sock = FakeSocket()
        ctrl = controller([sock])
        ctrl.set_colour(10, 20, 30)
        self.assertEqual(sock.sent[-1][5], proto.MASK_COLOUR)

    def test_commands_are_paced_so_a_burst_is_not_dropped(self):
        sock = FakeSocket()
        ctrl = controller([sock])
        started = time.time()
        for _ in range(5):
            ctrl.turn_on()
        self.assertGreaterEqual(time.time() - started, mdev.MIN_COMMAND_GAP * 3)
        self.assertEqual(len(sock.sent), 5)


class TestBackoff(unittest.TestCase):

    def test_backoff_stops_the_next_attempt_costing_a_timeout(self):
        ctrl = controller([FakeSocket(fail_on_send=True), FakeSocket(fail_on_send=True)])
        ctrl.turn_on()
        self.assertTrue(ctrl.in_backoff)
        self.assertFalse(ctrl.turn_on())

    def test_backoff_grows_but_is_capped(self):
        ctrl = controller([])
        for _ in range(12):
            ctrl._note_failure("gone")
        self.assertLessEqual(ctrl._retry_after - time.time(), mdev.BACKOFF_MAX + 1)

    def test_a_controller_in_backoff_is_still_reachable_when_forced(self):
        sock = FakeSocket()
        ctrl = controller([sock])
        ctrl._note_failure("gone")
        self.assertTrue(ctrl.send(proto.power(True), force=True))

    def test_success_clears_the_backoff(self):
        dead, good = FakeSocket(fail_on_send=True), FakeSocket()
        ctrl = controller([dead, good])
        ctrl.turn_on()
        self.assertFalse(ctrl.in_backoff)
        self.assertEqual(ctrl.failures, 0)


class TestReadingState(unittest.TestCase):

    def test_a_query_returns_the_parsed_state(self):
        ctrl = controller([FakeSocket()])
        state = ctrl.read_state()
        self.assertIsNotNone(state)
        self.assertEqual(state.rgb, (255, 0, 0))
        self.assertTrue(state.is_on)

    def test_unsolicited_pushes_do_not_corrupt_the_reading(self):
        # The failure this guards against produced readings that were pure
        # noise but looked entirely plausible.
        ctrl = controller([FakeSocket(pushes=REAL_PUSH)])
        state = ctrl.read_state()
        self.assertIsNotNone(state)
        self.assertEqual(state.rgb, (255, 0, 0))

    def test_a_junk_reply_yields_none_not_an_invented_reading(self):
        ctrl = controller([FakeSocket(reply_junk=True), FakeSocket(reply_junk=True)])
        self.assertIsNone(ctrl.read_state())
        self.assertFalse(ctrl.available)

    def test_none_means_unknown_and_never_means_off(self):
        ctrl = controller([])
        self.assertIsNone(ctrl.read_state())
        self.assertIsNone(ctrl.last_state)

    def test_the_model_byte_is_learned_from_the_first_reply(self):
        sock = FakeSocket()
        ctrl = mdev.Controller("192.168.1.50", model_num=None, timeout=0.3,
                               connect_factory=lambda *a: sock)
        ctrl.read_state()
        self.assertEqual(ctrl.model_num, 0x06)

    def test_the_query_is_sent_after_the_buffer_is_drained(self):
        sock = FakeSocket(pushes=REAL_PUSH)
        ctrl = controller([sock])
        ctrl.read_state()
        self.assertEqual(sock.sent[-1], proto.query())


class TestDiscovery(unittest.TestCase):

    def test_finds_a_controller(self):
        udp = FakeUdpSocket([b"192.168.1.50,806A34112233,AK001-ZJ21413,uuid"])
        found = mdev.discover(timeout=0.2, socket_factory=lambda: udp)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].ip, "192.168.1.50")

    def test_broadcast_is_actually_enabled(self):
        udp = FakeUdpSocket([])
        mdev.discover(timeout=0.2, socket_factory=lambda: udp)
        self.assertTrue(any(name == socket.SO_BROADCAST for _l, name, _v in udp.options))

    def test_our_own_probe_coming_back_is_ignored(self):
        udp = FakeUdpSocket([proto.DISCOVERY_PROBE,
                             b"192.168.1.9,AABBCCDDEEFF,AK001-ZJ200,uuid"])
        found = mdev.discover(timeout=0.2, socket_factory=lambda: udp)
        self.assertEqual(len(found), 1)

    def test_duplicate_replies_collapse_to_one_controller(self):
        udp = FakeUdpSocket([b"192.168.1.9,AABBCCDDEEFF,AK001-ZJ200,uuid"] * 3)
        self.assertEqual(len(mdev.discover(timeout=0.2, socket_factory=lambda: udp)), 1)

    def test_rubbish_replies_are_dropped_not_half_parsed(self):
        udp = FakeUdpSocket([b"nonsense", b"192.168.1.9,AABBCCDDEEFF,AK001,uuid"])
        self.assertEqual(len(mdev.discover(timeout=0.2, socket_factory=lambda: udp)), 1)

    def test_a_broken_network_yields_an_empty_list_not_an_exception(self):
        udp = FakeUdpSocket([], raise_on_send=OSError("network is down"))
        self.assertEqual(mdev.discover(timeout=0.2, socket_factory=lambda: udp), [])

    def test_the_socket_is_always_closed(self):
        udp = FakeUdpSocket([])
        mdev.discover(timeout=0.2, socket_factory=lambda: udp)
        self.assertTrue(udp.closed)

    def test_resolve_ip_finds_a_moved_controller(self):
        udp = FakeUdpSocket([b"192.168.1.99,806A34112233,AK001-ZJ21413,uuid"])
        self.assertEqual(
            mdev.resolve_ip("80:6a:34:11:22:33", timeout=0.2, socket_factory=lambda: udp),
            "192.168.1.99")

    def test_resolve_ip_returns_none_when_it_did_not_answer(self):
        udp = FakeUdpSocket([b"192.168.1.9,AABBCCDDEEFF,AK001,uuid"])
        self.assertIsNone(
            mdev.resolve_ip("806A34112233", timeout=0.2, socket_factory=lambda: udp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
