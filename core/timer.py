#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import weakref
import ctypes


def uint32(n):
    return ctypes.c_uint32(n).value


class Timer(object):

    def __init__(self):
        self.handler = None
        self.pos = 0

        self.prev = self.next = weakref.proxy(self)

    def __del__(self):
        self.remove()

        self.prev = None
        self.next = None
        self.handler = None

    def empty(self):
        return self.prev == self.next

    def remove(self):
        if self.empty():
            return
        self.prev.next = self.next
        self.next.prev = self.prev

        self.prev = self.next = weakref.proxy(self)

        self.handler = None
        self.pos = 0


class TimerWheel(object):

    def __init__(self):
        self.__current = 0x7fffff00
        self.__expires = Timer()

        def init_tv(size):
            tv = []
            for i in range(size):
                t = Timer()
                tv.append(t)
            return tv
        self.__tv0 = init_tv(1 << 8)
        self.__tv1 = init_tv(1 << 6)
        self.__tv2 = init_tv(1 << 6)
        self.__tv3 = init_tv(1 << 6)
        self.__tv4 = init_tv(1 << 6)

    def __del__(self):
        self.__expires = None
        self.__tv0 = None
        self.__tv1 = None
        self.__tv2 = None
        self.__tv3 = None
        self.__tv4 = None

    def add_timer(self, t, jiffies):
        t.remove()

        t.pos = uint32(self.__current + jiffies)
        self.__add_timer(t)

    def del_timer(self, t):
        t.remove()

    def __add_timer(self, t):
        h = self.get_pos(t)

        t.prev = h.prev
        t.prev.next = t
        t.next = h
        h.prev = t

    def __add_queue(self, q):
        h = self.__expires

        h.prev.next = q.next
        q.next.prev = h.prev
        h.prev = q.prev
        h.prev.next = h

        q.prev = q.next = weakref.proxy(q)

    def __rebuild_tvs(self, jiffies):
        last = self.__current,
        self.__current = uint32(self.__current + jiffies)
        data = {
            'last': last,
            'tv_last': last,
            'tv_curr': self.__current,
        }

        def tv_expire(tv_to, tv_fr):
            if data['tv_last'] < data['tv_curr']:
                data['tv_last'] /= len(tv_fr)
            else:
                data['tv_last'] = uint32(~(uint32(~data['tv_last']) / len(tv_fr)))
            data['tv_curr'] /= len(tv_fr)
            if data['tv_last'] == data['tv_curr']:
                return
            loop = data['tv_curr'] - data['tv_last']
            if loop >= len(tv_to):
                loop = len(tv_to)
            for i in range(1, loop + 1):
                h = tv_to[uint32(data['tv_last'] + i) % len(tv_to)]
                while not h.empty():
                    t = h.next
                    t.remove()
                    if uint32(t.pos - data['last']) < jiffies:
                        h = self.__expires

                        t.prev = h.prev
                        t.prev.next = t
                        t.next = h
                        h.prev = t
                    else:
                        self.__add_timer(t)

        tv_expire(self.__tv1, self.__tv0)
        tv_expire(self.__tv2, self.__tv1)
        tv_expire(self.__tv3, self.__tv2)
        tv_expire(self.__tv4, self.__tv3)

    def process_expire(self, jiffies):
        if jiffies <= 0:
            return

        if jiffies < len(self.__tv0):
            loop = jiffies
        else:
            loop = len(self.__tv0)

        for i in range(loop):
            j = uint32(self.__current + i) % len(self.__tv0)
            q = self.__tv0[j]
            self.__add_queue(q)

        self.__rebuild_tvs(jiffies)

        while not self.__expires.empty():
            t = self.__expires.next
            t.remove()

            if t.handler:
                t.handler()

    def get_pos(self, t):
        data = {
            'jiffies': uint32(t.pos - self.__current),
            'current': t.pos,
        }

        def get_tv_pos(tv):
            data['jiffies'] /= len(tv)
            if data['jiffies'] == 0:
                data['current'] %= len(tv)
                return tv[data['current']]
            data['current'] /= len(tv)
            return None

        head = get_tv_pos(self.__tv0)
        if head:
            return head
        head = get_tv_pos(self.__tv1)
        if head:
            return head
        head = get_tv_pos(self.__tv2)
        if head:
            return head
        head = get_tv_pos(self.__tv3)
        if head:
            return head
        head = get_tv_pos(self.__tv4)
        if head:
            return head


__tw = TimerWheel()


def add_timer(t, jiffies):
    return __tw.add_timer(t, jiffies)


def del_timer(t):
    return __tw.del_timer(t)


def process_expire(jiffies):
    return __tw.process_expire(jiffies)
