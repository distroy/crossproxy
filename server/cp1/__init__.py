#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import time
import sys
import struct

from core import auth
from core import log
from core.connection import Connection
from core.timer import *
from core.addr import Addr

from event.event import *

from server.bridge import Bridge
from server.message import Message


HEARTBEAT_TIMEOUT = 120
HEARTBEAT_INTERVAL = 30
TIMESTAMP_INTERVAL = 30

RAND_CACHE = {}


class Enity(object):
    def __init__(self):
        self.DO_MAP = {
            'heartbeat rsp': Enity.do_heartbeat,
            'register rsp': Enity.do_register,
            'cross req': Enity.do_cross,
        }

    def set_opts(self, opts):
        proxy = Addr()
        target = Addr()
        if not proxy.parse(opts.proxy):
            log.error(0, 'invalid proxy address. %s', opts.proxy)
            return None
        if not target.parse(opts.target):
            log.error(0, 'invalid target address. %s', opts.target)
            return None
        if not opts.key:
            log.error(0, 'empty key.')
            return None
        if not opts.secret:
            log.error(0, 'empty secret.')
            return None

        self.conn = None
        self.addr_proxy = proxy
        self.addr_target = target
        self.key = opts.key
        self.secret = opts.secret

        self.addr_proxy.set_tcp()
        self.addr_target.set_tcp()

        self.stimer = None
        self.rtimer = None
        self.registered = False
        return self

    def is_valid(self):
        return self.addr_proxy and self.addr_target and addr.key

    def clear(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.stimer:
            del_timer(self.stimer)
            self.stimer.prev = self.stimer.next = None
            self.stimer = None
        if self.rtimer:
            del_timer(self.rtimer)
            self.rtimer.prev = self.rtimer.next = None
            self.rtimer = None
        self.registered = False

    def close(self):
        self.init()

    def init(self):
        addr = self.addr_proxy
        while True:
            self.clear()
            self.conn = Connection()
            if self.conn.connect(addr):
                break
            time.sleep(3)
            # if not addr.next_sockaddr():
            #     sys.exit(-1)

        c = self.conn
        log.debug(0, '*%d connect: %s', c.index, c.addr.text)
        c.nonblocking()
        self.send_msg(['register req', self.key])

        self.stimer = Timer()
        self.stimer.handler = lambda: self.on_stimer()
        add_timer(self.stimer, HEARTBEAT_INTERVAL)

        self.rtimer = Timer()
        self.rtimer.handler =lambda: self.on_rtimer()
        add_timer(self.rtimer, HEARTBEAT_TIMEOUT)

    def on_stimer(self):
        if not self.registered:
            self.close()
            return
        add_timer(self.stimer, HEARTBEAT_INTERVAL)
        self.send_msg(['heartbeat req'])

    def on_rtimer(self):
        log.warn(0, 'connect has close')
        self.close()

    def send(self):
        c = self.conn
        buff = c.wev.buff
        if len(buff) > 0:
            r, size = c.send(buff)
            if r != 0:
                if r == 1:
                    log.debug(0, '*%d closed', c.index)
                self.close()
                return
            c.wev.buff = buff[size:]

        if len(buff) > 0:
            c.wev.handler = lambda: self.send()
            del_conn(c, READ_EVENT)
            add_conn(c, WRITE_EVENT)
        else:
            c.rev.handler = lambda: self.read()
            del_conn(c, WRITE_EVENT)
            add_conn(c, READ_EVENT)

    def send_bin(self, buff):
        c = self.conn
        c.wev.buff = ''.join([c.wev.buff, struct.pack('I', len(buff)), buff])
        self.send()

    def send_msg(self, msg):
        c = self.conn
        if isinstance(msg, str) or isinstance(msg, list) or isinstance(msg, Message):
            msg = Message(msg)
        if msg.get(0) != 'heartbeat req':
            log.debug(0, '*%d send message: %s', c.index, msg)
        else:
            log.trace(0, '*%d send message: %s', c.index, msg)

        buff = msg.encode()
        if not buff:
            log.error(0, 'invalid message: %s', msg)
            return
        self.send_bin(buff)

    def read(self):
        buff = self.read_bin()
        if not buff:
            return

        msg = Message()
        r = msg.decode(buff)
        if r != 0:
            return
        if r < 0:
            self.close()
            return

        self.process(msg)

    def read_bin(self):
        c = self.conn
        r, buff = c.recv(4096)
        if r != 0:
            if r == 1:
                log.debug(0, '*%d closed', c.index)
            self.close()
            return ''
        c.rev.buff += buff
        buff = c.rev.buff

        size0 = struct.calcsize('I')
        if len(buff) < size0:
            return ''

        size1, = struct.unpack('I', buff[0: size0])
        if len(buff) < size1 + size0:
            return ''

        c.rev.buff = buff[size0 + size1:]
        return buff[size0: size0 + size1]

    def process(self, msg):
        c = self.conn
        cmd = msg.get(0)
        if cmd != 'heartbeat rsp':
            log.debug(0, '*%d read message: %s', c.index, msg)
        else:
            log.trace(0, '*%d read message: %s', c.index, msg)

        if not self.DO_MAP.has_key(cmd):
            log.error(0, 'invalid command. msg:%s', msg)
            return

        add_timer(self.stimer, HEARTBEAT_INTERVAL)
        add_timer(self.rtimer, HEARTBEAT_TIMEOUT)
        self.DO_MAP[cmd](self, msg)

    def do_heartbeat(self, msg):
        return

    def do_register(self, msg):
        err = msg.get(1)
        if err != 'ok':
            log.error(0, 'register fail. msg:%s', msg)
            self.send_msg(['register req', self.key])
            return

        self.registered = True
        log.debug(0, 'register succ. key:%s', self.key)

    def do_cross(self, msg):
        ckey = msg.get(1)
        if not ckey:
            log.error(0, 'invalid message. msg:%s', msg)
            self.send_msg(['cross rsp', 'error', 'empty connect key'])
            return

        now = int(time.time())
        timestamp = int(msg.get(2))
        if abs(now - timestamp) > TIMESTAMP_INTERVAL:
            log.error(0, 'invalid timestamp. msg:%s', msg)
            self.send_msg(['cross rsp', 'error', 'invalid timestamp', ckey])
            return

        rand = msg.get(3)
        if RAND_CACHE.has_key(rand):
            log.error(0, 'duplicate rand str. msg:%s', msg);
            self.send_msg(['cross rsp', 'error', 'invalid rand', ckey])
            return

        sign = auth.get_sign(self.secret, [timestamp, rand])

        if sign != msg.get(4):
            log.error(0, 'check auth fail. msg:%s, expected sign:%s', msg, sign)
            self.send_msg(['cross rsp', 'error', 'auth fail', ckey])
            return

        RAND_CACHE[rand] = 1
        timer = Timer()
        timer.handler = lambda: RAND_CACHE.pop(rand)
        add_timer(timer, TIMESTAMP_INTERVAL * 2)

        t = Cross(self.addr_proxy, self.addr_target, ckey)
        t.init()
        self.send_msg(['cross rsp', 'ok', ckey])


class Cross(object):
    def __init__(self, proxy, target, ckey):
        self.addr_proxy = proxy
        self.addr_target = target

        self.conn_proxy = None
        self.conn_target = None

        self.ready_proxy = False
        self.ready_target = False

        self.key = ckey

    def init(self):
        self.conn_proxy = Connection()
        self.conn_target = Connection()

        c = self.conn_proxy
        c.connect_nonblocking(self.addr_proxy)
        c.wev.handler = lambda: self.ready_connect_proxy()
        add_conn(c, WRITE_EVENT)

        c = self.conn_target
        c.connect_nonblocking(self.addr_target)
        c.wev.handler = lambda: self.ready_connect_target()
        add_conn(self.conn_target, WRITE_EVENT)

    def close(self):
        if self.conn_proxy:
            self.conn_proxy.close()
            self.conn_proxy = None
        if self.conn_target:
            self.conn_target.close()
            self.conn_target = None

    def ready_connect_proxy(self):
        c = self.conn_proxy
        log.debug(0, '*%d connect: %s', c.index, c.addr.text)

        msg = Message(['accept req', self.key])
        log.debug(0, '*%d send message: %s', c.index, msg)

        buff = msg.encode()
        if not buff:
            log.error(0, 'invalid message: %s', msg)
            return

        c.wev.buff = struct.pack('I', len(buff)) + buff
        c.wev.handler = lambda: self.send()
        self.send()

    def ready_connect_target(self):
        c = self.conn_target
        log.debug(0, '*%d connect: %s', c.index, c.addr.text)
        del_conn(c, WRITE_EVENT)

        self.ready_target = True
        self.check_ready()

    def send(self):
        c = self.conn_proxy
        buff = c.wev.buff
        if len(buff) > 0:
            r, size = c.send(buff)
            if r != 0:
                if r == 1:
                    log.debug(0, '*%d closed', c.index)
                self.close()
                return
            c.wev.buff = buff[size:]

        buff = c.wev.buff
        if len(buff) > 0:
            c.wev.handler = lambda: self.send()
            del_conn(c, READ_EVENT)
            add_conn(c, WRITE_EVENT)
        else:
            c.rev.handler = lambda: self.read()
            del_conn(c, WRITE_EVENT)
            add_conn(c, READ_EVENT)

    def read(self):
        buff = self.read_bin()
        if not buff:
            return

        msg = Message()
        r = msg.decode(buff)
        if r != 0:
            return
        if r < 0:
            self.close()
            return

        c = self.conn_proxy
        log.debug(0, '*%d read message. msg:%s', c.index, msg)

        cmd = msg.get(0)
        if cmd != 'accept rsp':
            log.error(0, 'invalid message. msg:%s', msg)
            self.close()
            return

        err = msg.get(1)
        if err != 'ok':
            log.error(0, 'accept fail. msg:%s', msg)
            self.close()
            return
        self.ready_proxy = True
        del_conn(c, WRITE_EVENT)
        self.check_ready()

    def read_bin(self):
        c = self.conn_proxy
        r, buff = c.recv(4096)
        if r != 0:
            if r == 1:
                log.debug(0, '*%d closed', c.index)
            self.close()
            return ''
        c.rev.buff += buff
        buff = c.rev.buff

        size0 = struct.calcsize('I')
        if len(buff) < size0:
            return ''

        size1, = struct.unpack('I', buff[0: size0])
        if len(buff) < size1 + size0:
            return ''

        c.rev.buff = buff[size0 + size1:]
        return buff[size0: size0 + size1]

    def check_ready(self):
        if self.ready_target:
            self.conn_target.wev.handler = None
            del_conn(self.conn_target, WRITE_EVENT)

        if self.ready_proxy:
            self.conn_proxy.wev.handler = None
            del_conn(self.conn_proxy, WRITE_EVENT)

        if self.ready_proxy and self.ready_target:
            Bridge(self.conn_proxy, self.conn_target)
            self.conn_proxy = None
            self.conn_target = None
