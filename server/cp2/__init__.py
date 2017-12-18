#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import hashlib
import struct
import time
import random

from core import log
from core.addr import Addr
from core.connection import Connection
from core import closure
from core.timer import *

from server.bridge import Bridge
from server.message import Message

from event.event import *


REGISTER = {}
CONNECT = {}
EXPIRE_TIME = 60


get_sequence = closure(0, lambda x: (x + 1) & 0xfffffff)


def get_handler(opts, args):
    if not opts.key:
        log.error(0, 'empty key.')
        return None
    if not opts.secret:
        log.error(0, 'empty secret.')
        return None
    addr = Addr()
    if not addr.parse(opts.proxy):
        log.error(0, 'invalid proxy address. %s', opts.proxy)
        return None
    return lambda c: Enity(c, addr, opts)


class Enity(object):

    def __init__(self, c, addr, opts):
        self.conn = c

        self.key = opts.key
        self.secret = opts.secret
        self.addr_proxy = addr

        self.conn_proxy = Connection()
        c = self.conn_proxy
        if not c.connect_nonblocking(addr):
            self.close()
            return

        c.wev.handler = lambda: self.send_connect()
        add_conn(c, WRITE_EVENT)

        self.timer = Timer()
        self.timer.handler = lambda: self.on_timeout()
        add_timer(self.timer, EXPIRE_TIME)

    def on_timeout(self):
        c = self.conn_proxy
        log.warn(0, '*%d timeout', c.index)
        self.close()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

        if self.conn_proxy:
            self.conn_proxy.close()
            self.conn_proxy = None

        if self.timer:
            del_timer(self.timer)
            self.timer = None

    def send_connect(self):
        c = self.conn_proxy
        log.debug(0, '*%d connect: %s', c.index, c.addr.text)

        timestamp = int(time.time())
        rand = '%x_%d' % (random.randint(0, 0xffffffff), get_sequence())
        md5 = hashlib.md5('|'.join([self.secret, timestamp, rand])).hexdigest()

        msg = Message(['connect req', self.key,  timestamp, rand, md5])
        log.debug(0, '*%d send message: %s', c.index, msg)

        buff = msg.encode()
        if not buff:
            log.error(0, 'invalid message: %s', msg)
            return

        c.wev.buff = struct.pack('I', len(buff)) + buff
        c.wev.handler = lambda: self.send()
        self.send()

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
            c.rev.handler = lambda: self.read_connect()
            del_conn(c, WRITE_EVENT)
            add_conn(c, READ_EVENT)

    def read_bin(self):
        c = self.conn_proxy
        r, buff = c.recv(4096)
        if r != 0:
            if r == 1:
                log.debug(0, '*%d closed', self.conn.index)
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

    def read_connect(self):
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
        log.debug(0, '*%d read message: %s', c.index, msg)

        cmd = msg.get(0)
        if cmd != 'connect rsp':
            log.error(0, 'invalid command. msg:%s', msg)
            return

        err = msg.get(1)
        if err != 'ok':
            log.error(0, 'accept fail. msg:%s', msg)
            self.close()
            return

        Bridge(self.conn, self.conn_proxy)
        self.conn = None
        self.conn_proxy = None

        if self.timer:
            del_timer(self.timer)
            self.timer = None
