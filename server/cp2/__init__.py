#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import struct

from core import log
from core.addr import Addr
from core.connection import Connection
from core import closure

from server.bridge import Bridge
from server.message import Message

from event.event import *


REGISTER = {}
CONNECT = {}


get_sequence = closure(0, lambda x: (x + 1) & 0xfffffff)


def get_handler(opts, args):
    key = opts.key
    addr = Addr()
    if not addr.parse(opts.proxy):
        log.error(0, 'invalid proxy address: %s', opts.proxy)
        return None
    return lambda c: Enity(c, key, addr)


class Enity(object):

    def __init__(self, c, key, addr):
        self.conn = c

        self.key = key
        self.addr_proxy = addr

        self.conn_proxy = Connection()
        c = self.conn_proxy
        if not c.connect_nonblocking(addr):
            self.close()
            return

        c.wev.handler = lambda: self.send_connect()
        add_conn(c, WRITE_EVENT)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

        if self.conn_proxy:
            self.conn_proxy.close()
            self.conn_proxy = None

    def send_connect(self):
        msg = Message(['connect req', self.key])
        log.debug(0, 'send message: %s', msg)

        buff = msg.encode()
        if not buff:
            log.error(0, 'invalid message: %s', msg)
            return
        self.conn_proxy.wev.buff = buff
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
        if len(buff) > 0:
            c.wev.handler = lambda: self.send()
            del_conn(c, READ_EVENT)
            add_conn(c, WRITE_EVENT)
        else:
            c.rev.handler = lambda: self.read_connect()
            del_conn(c, WRITE_EVENT)
            add_conn(c, READ_EVENT)

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

        size1, = struct.unpack('I', buff[0: size0)
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

        log.debug(0, 'read message: %s', msg)

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
