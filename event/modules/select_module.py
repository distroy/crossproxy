#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import select

from core import log
from event.event import *


class Select(object):
    name = 'select'

    def __init__(self):
        self.r_list = []    # read
        self.w_list = []    # write
        self.x_list = []    # exception

        self.r_datas = {}
        self.w_datas = {}

        self.__ = self

    def __del__(self):
        self.done()

    def done(self):
        for s in self.r_datas:
            ev, c = self.r_datas[s]
            ev.active = False

        for s in self.w_datas:
            ev, c = self.w_datas[s]
            ev.active = False

        self.r_list = []    # read
        self.w_list = []    # write
        self.x_list = []    # exception

        self.r_datas = {}
        self.w_datas = {}

    def add_conn(self, c, event, flag = 0):
        s   = c.socket()
        wev = c.wev
        rev = c.rev
        e   = 0

        if event & READ_EVENT and not rev.active:
            e |= READ_EVENT
            self.r_list.append(s)
            self.r_datas[s] = (rev, c)  # 防止connection过早释放
            rev.active      = self      # 防止select过早释放

        if event & WRITE_EVENT and not wev.active:
            e |= WRITE_EVENT
            self.w_list.append(s)
            self.w_datas[s] = (wev, c)  # 防止connection过早释放
            wev.active      = self      # 防止select过早释放

        return e

    def del_conn(self, c, event, flag = 0):
        s   = c.socket()
        wev = c.wev
        rev = c.rev
        e   = 0

        if not wev.active and not rev.active:
            return

        if event & READ_EVENT and rev.active:
            e |= READ_EVENT
            self.r_list.remove(s)
            del self.r_datas[s]
            rev.active = None

        if event & WRITE_EVENT and wev.active:
            e |= WRITE_EVENT
            self.w_list.remove(s)
            del self.w_datas[s]
            wev.active = None

        return e

    def process_events(self, wait_time = 20):
        if wait_time:
            wait_time = [float(wait_time) % 1000]
        else:
            wait_time = []
        try:
            r, w, x = select.select(self.r_list, self.w_list, self.x_list, *wait_time)
        except Exception as exc:
            log.error(exc, 'select() failed')
            exit(-1)
            return

        if not (r or w or x):
            return

        closed = {}

        for s in r:
            if not self.r_datas.has_key(s):
                continue
            ev, c = self.r_datas[s]
            if not c.socket():
                closed[s] = c
                continue

            ev.process(self.name)

        for s in w:
            if not self.w_datas.has_key(s):
                continue
            ev, c = self.w_datas[s]
            if not c.socket():
                closed[s] = c
                continue

            ev.process(self.name)

        for s in closed:
            c = closed[s]
            if c.wev.active:
                self.w_list.remove(s)
                del self.w_datas[s]
            if c.rev.active:
                self.r_list.remove(s)
                del self.r_datas[s]
