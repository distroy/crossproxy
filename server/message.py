#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import struct


class Message(object):
    def __init__(self, msg = [], seq = 0):
        if isinstance(msg, str):
            msg = [msg]
        elif isinstance(msg, Message):
            seq = msg.__seq
            msg = msg.__msg
        elif not isinstance(msg, list):
            msg = []
        self.__msg = []
        self.__seq = seq
        self.__msg.extend(msg)

    def clear(self):
        self.__msg = []
        self.__seq = 0

    def set_sequence(self, seq):
        self.__seq = seq

    def get_sequence(self):
        return self.__seq

    def get(self, idx):
        if len(self.__msg) < idx + 1:
            return ''
        return self.__msg[idx]

    def set(self, idx, val):
        while len(self.__msg) < idx + 1:
            self.__msg.append('')
        self.__msg[idx] = val


    def encode(self):
        msg = self.__msg
        if len(msg) == 0:
            return ''

        self.size = 0
        buff = []

        def pack(fmt, val):
            buff.append(struct.pack(fmt, val))
            self.size += struct.calcsize(fmt)

        pack('I', self.__seq)
        pack('B', len(msg))
        for i in msg:
            l = len(i)
            pack('H', l)
            pack('%ds' % l, i)

        return ''.join(buff)

    def decode(self, buff):
        self.clear()
        self.pos = 0

        def unpack(fmt):
            l = struct.calcsize(fmt)
            if len(buff) < self.pos + l:
                return None
            v = struct.unpack(fmt, buff[self.pos: self.pos + l])
            self.pos += l
            return v

        msg = []

        self.__seq, = unpack('I')
        n, = unpack('B')
        if not n:
            return -1

        for i in range(n):
            l, = unpack('H')
            if not l:
                return -1
            s, = unpack('%ds' % l)
            if not s:
                return -1
            msg.append(s)

        self.__msg = msg
        return 0

    def __str__(self):
        return '{id:%d, body:%s}' % (self.__seq, self.__msg)
