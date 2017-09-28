#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import time
import struct

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


get_sequence = closure(0, lambda x: (x + 1) & 0xfffffff)


def get_handler(opts, args):
    return lambda c: Enity(c)

class Enity(object):

    def __init__(self, c):
        self.DO_MAP = {
            'heartbeat req': Enity.do_heartbeat,
            'register req': Enity.do_register,
            'connect req': Enity.do_connect,
            'accept req': Enity.do_accept,
            'cross rsp': Enity.do_cross,
        }

        self.conn = c

        self.register_key = None
        self.connect_key = None

        c.rev.handler = lambda: self.read()
        add_conn(c, READ_EVENT)

        self.timer = Timer()
        self.timer.handler = lambda: self.close()

    def close(self):
        if self.register_key:
            log.debug(0, '*%d del register: %s', self.conn.index, self.register_key)
            del REGISTER[self.register_key]
            self.register_key = None

        if self.connect_key:
            log.debug(0, '*%d del connect: %s', self.conn.index, self.connect_key)
            del CONNECT[self.connect_key]
            self.connect_key = None

        if self.conn:
            self.conn.close()
            self.conn = None

        if self.timer:
            del_timer(self.timer)
            self.timer.prev = self.timer.next = None
            self.timer = None


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

    def send_bin(self, buff):
        c = self.conn
        c.wev.buff = ''.join([c.wev.buff, struct.pack('I', len(buff)), buff])
        self.send()

    def send_msg(self, msg):
        if isinstance(msg, str) or isinstance(msg, list) or isinstance(msg, Message):
            msg = Message(msg)

        c = self.conn
        log.debug(0, '*%d send message: %s', c.index, msg)

        buff = msg.encode()
        if not buff:
            log.error(0, 'invalid message: %s', msg)
            return
        self.send_bin(buff)

    def process(self, msg):
        c = self.conn
        log.debug(0, '*%d read message: %s', c.index, msg)

        cmd = msg.get(0)
        if not self.DO_MAP.has_key(cmd):
            log.error(0, 'invalid command. msg:%s', msg)
            return

        add_timer(self.timer, 120)
        self.DO_MAP[cmd](self, msg)


    def do_heartbeat(self, msg):
        self.send_msg(['heartbeat rsp'])

    def do_register(self, msg):
        key = msg.get(1)
        if not key:
            log.error(0, 'invalid message: %s', msg)
            return

        if self.connect_key:
            log.error(0, '*%d has connected. key:%s', self.connect_key)
            self.send_msg(['connect rsp', 'error', 'has connected. key:%s' % self.connect_key])
            return

        if self.register_key:
            if self.register_key != key:
                log.error(0, '*%d has registered, key:%s', self.conn.index, self.register_key)
                self.send_msg(['register rsp', 'error', 'has registered other'])
            else:
                self.send_msg(['register rsp', 'ok'])
            return

        if REGISTER.has_key(key):
            self.send_msg(['register rsp', 'error', 'has registered. key:%s' % key])
            return

        REGISTER[key] = self
        self.register_key = key
        log.debug(0, '*%d add register: %s', self.conn.index, self.register_key)
        self.send_msg(['register rsp', 'ok'])

    def do_accept(self, msg):
        key = msg.get(1)
        if not key:
            log.error(0, 'invalid message: %s', msg)
            return

        if self.register_key:
            log.error(0, '*%d has registered. key:%s', self.register_key)
            self.send_msg(['connect rsp', 'error', 'has registered. key:%s' % self.register_key])
            return

        if self.connect_key:
            log.error(0, '*%d has connected. key:%s', self.connect_key)
            self.send_msg(['connect rsp', 'error', 'has connected. key:%s' % self.connect_key])
            return

        if not CONNECT.has_key(key):
            self.send_msg(['accept rsp', 'error', 'has not connect. key:%s' % key])
            return

        e = CONNECT[key]
        log.debug(0, '*%d del connect: %s', e.conn.index, e.connect_key)
        del CONNECT[key]
        e.connect_key = None

        self.send_msg(['accept rsp', 'ok'])
        e.send_msg(['connect rsp', 'ok'])

        if e.conn and self.conn:
            Bridge(e.conn, self.conn)
            e.conn = None
            e.timer = None
            self.conn = None
            self.timer = None
        else:
            e.close()
            self.close()

    def do_connect(self, msg):
        key0 = msg.get(1)
        if not key0:
            log.error(0, 'invalid message: %s', msg)
            return

        if self.register_key:
            log.error(0, '*%d has registered. key:%s', self.register_key)
            self.send_msg(['connect rsp', 'error', 'has registered. key:%s' % self.register_key])
            return

        if self.connect_key:
            log.error(0, '*%d has connected. key:%s', self.connect_key)
            self.send_msg(['connect rsp', 'error', 'has connected. key:%s' % self.connect_key])
            return

        if not REGISTER.has_key(key0):
            log.error(0, 'can not find the register. key:%s', key0)
            self.send_msg(['connect rsp', 'error', 'can not find the register. key:%s' % key0])
            return

        key1 = '%s_%08x' % (time.strftime('%Y%m%d%H%M%S'), get_sequence())
        CONNECT[key1] = self
        self.connect_key = key1

        e = REGISTER[key0]
        e.send_msg(['cross req', key1])


    def do_cross(self, msg):
        err = msg.get(1)
        if err != 'ok':
            log.error(0, 'cross fail. msg:%s', msg)
        return
