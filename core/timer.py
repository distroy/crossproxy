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
        self.__tv0 = init_tv(1 << 8)
        self.__tv1 = init_tv(1 << 6)
        self.__tv2 = init_tv(1 << 6)
        self.__tv3 = init_tv(1 << 6)
        self.__tv4 = init_tv(1 << 6)

    def add_timer(self, t, jiffies):
        t.remove()

        t.pos = uint32(self.__current + jiffies)
        self.__add(t)


    def del_timer(self, t):
        t.remove()


    def __add(self, t):
        h = self.get_pos(t)

        t.prev = h.prev
        t.prev.next = t
        t.next = h
        h.prev = t


    def process_expire(jiffies):
        if jiffies <= 0:
            return


    def get_pos(self, t):
        data = {
            'jiffies': uint32(t.pos - self.__current),
            'current': t.pos,
        }

        def get_tv_pos(tv):
            data['jiffies'] /= len(tv)
            if (data['jiffies'] == 0) {
                data['current'] %= len(tv)
                return tv[data['current']]
            }
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


def add_timer(t):
    return __tw.add_timer(t)
