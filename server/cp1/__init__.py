#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import time
import sys
import struct

from core import log
from core.connection import Connection
from core.timer import *
from core.addr import Addr

from event.event import *

from server.bridge import Bridge
from server.message import Message


HEARTBEAT_INTERVAL = 30


class Enity(object):
    def __init__(self, proxy, target, key):
        self.DO_MAP = {
            'heartbeat rsp': Enity.do_heartbeat,
            'register rsp': Enity.do_register,
            'cross req': Enity.do_cross,
        }

        self.conn = None
        self.addr_proxy = proxy
        self.addr_target = target
        self.key = key

        self.addr_proxy.set_tcp()
        self.addr_target.set_tcp()

        self.timer = None

    def clear(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.timer:
            del_timer(self.timer)
            self.timer.prev = self.timer.next = None
            self.timer = None

    def close(self):
        self.init()

    def init(self):
        addr = self.addr_proxy
        while True:
            self.clear()
            self.conn = Connection()
            if self.conn.connect(addr):
                break
            time.sleep(1)
            # if not addr.next_sockaddr():
            #     sys.exit(-1)

        c = self.conn
        log.debug(0, '*%d connect: %s', c.index, c.addr.text)
        c.nonblocking()
        self.send_msg(['register req', self.key])

        self.timer = Timer()
        self.timer.handler = lambda : self.on_timer()
        add_timer(self.timer, HEARTBEAT_INTERVAL)

    def on_timer(self):
        add_timer(self.timer, HEARTBEAT_INTERVAL)
        self.send_msg(['heartbeat req'])

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
        log.debug(0, '*%d send message: %s', c.index, str(msg))

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
        log.debug(0, '*%d read message: %s', c.index, msg)

        cmd = msg.get(0)
        if not self.DO_MAP.has_key(cmd):
            log.error(0, 'invalid command. msg:%s', msg)
            return

        add_timer(self.timer, HEARTBEAT_INTERVAL)
        self.DO_MAP[cmd](self, msg)

    def do_heartbeat(self, msg):
        return

    def do_register(self, msg):
        err = msg.get(1)
        if err != 'ok':
            log.error(0, 'register fail. msg:%s', msg)
            self.send_msg(['register req', self.key])
            return

        log.debug(0, 'register succ. key:%s', self.key)

    def do_cross(self, msg):
        key = msg.get(1)
        if not key:
            log.error(0, 'invalid message: %s', msg)
            return

        t = Cross(self.addr_proxy, self.addr_target, key)
        t.init()
        self.send_msg(['cross rsp', 'ok', key])


class Cross(object):
    def __init__(self, proxy, target, key):
        self.addr_proxy = proxy
        self.addr_target = target

        self.conn_proxy = None
        self.conn_target = None

        self.ready_proxy = False
        self.ready_target = False

        self.key = key

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
