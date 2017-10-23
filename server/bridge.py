#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


from core import log
from core.timer import *

from event.event import *


EXPIRE_TIME = 120


class Bridge(object):
    def __init__(self, c0, c1):
        self.c0 = c0
        self.c1 = c1

        c0.rev.handler = c1.wev.handler = lambda: self.forward(c0, c1)
        c0.wev.handler = c1.rev.handler = lambda: self.forward(c1, c0)

        log.debug(0, '*%d connect: %s', c1.index, c1.addr.text)
        log.info(0, '*%d bridge *%d connect', c0.index, c1.index)

        del_conn(c0, WRITE_EVENT)
        del_conn(c1, WRITE_EVENT)

        add_conn(c0, READ_EVENT)
        add_conn(c1, READ_EVENT)

        self.timer = Timer()
        self.timer.handler = lambda: self.on_timeout()
        add_timer(self.timer, EXPIRE_TIME)


    def on_timeout(self):
        c0 = self.c0
        c1 = self.c1
        if c0.index < c1.index:
            i0 = c0.index
            i1 = c1.index
        else:
            i1 = c0.index
            i0 = c1.index
        log.warn(0, '*%d bridge *%d timeout', i0, i1)
        self.close()


    def forward(self, rc, wc):
        add_timer(self.timer, EXPIRE_TIME)
        log.trace(0, 'recv: *%d(%s)    send: *%d(%s)',
                  rc.index, rc.addr.text, wc.index, wc.addr.text)

        buff = rc.rev.buff
        while True:
            r = 0
            if not buff:
                r, buff = rc.recv(4096)
            if r != 0:
                if r == 1:
                    log.debug(0, '*%d closed', rc.index)
                rc.rev.ready = False
                break
            if not buff:
                rc.rev.buff = ''
                add_conn(rc, READ_EVENT)
                del_conn(wc, WRITE_EVENT)
                rc.rev.ready = False
                return

            r, size = wc.send(buff)
            if r != 0:
                if r == 1:
                    log.debug(0, '*%d closed', wc.index)
                wc.wev.ready = False
                break
            if not size:
                rc.rev.buff = buff
                del_conn(rc, READ_EVENT)
                add_conn(wc, WRITE_EVENT)
                wc.wev.ready = False
                return
            buff = buff[size:]

        if rc.index < wc.index:
            i0 = rc.index
            i1 = wc.index
        else:
            i1 = rc.index
            i0 = wc.index
        log.info(0, '*%d bridge *%d break', i0, i1)
        self.close()

    def close(self):
        self.c0.close()
        self.c1.close()
        self.c0 = None
        self.c1 = None
