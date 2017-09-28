#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import errno
import platform
import socket
import weakref

from core import log
from core import closure
from core.addr import Addr

from event.event import *


get_sequence = closure(0, lambda x: (x + 1) & 0xfffffff)

is_cygwin = platform.system().lower().find('cygwin') != -1


def create_socket(addr):
    try:
        s = socket.socket(addr.family, addr.socktype, addr.proto)
    except Exception as exc:
        log.error(exc, 'socket.socket(%s) failed', addr.text)
        return None

    log.trace(0, 'socket create: %d(%s) family:%r socktype:%r proto:%r',
              s.fileno(), addr.text, addr.family, addr.socktype, addr.proto)
    return s


def close_socket(s):
    try:
        if isinstance(s, socket.socket):
            s.shutdown(socket.SHUT_RDWR)
            log.trace(0, 'socket close: %d', s.fileno())
    except Exception as exc:
        log.error(exc, 'socket.shutdown(%d) failed', s.fileno())


class Connection():
    index = -1

    wev = None
    rev = None

    sock = None
    addr = None
    listening = None

    def __init__(self):
        self.index = get_sequence()
        log.trace(0, 'connection create *%d', self.index)
        if is_cygwin and self.index > 500:
            exit(0)

        # 防止循环引用，无法释放
        self.wev = Event(weakref.proxy(self))
        self.rev = Event(weakref.proxy(self))

        self.wev.write = True
        self.rev.read = True

        self.sock = None

    def __del__(self):
        self.close()
        log.trace(0, 'connection destroy *%d', self.index)

    def socket(self, s=None):
        if isinstance(s, Addr) or isinstance(s, socket.socket):
            if isinstance(s, Addr):
                s = create_socket(s)
            elif isinstance(s, socket.socket):
                s = s.dup()

            self.close()
            self.sock = s
            log.trace(0, 'connection socket *%d: %d', self.index, s.fileno())

        return self.sock

    def close(self):
        if self.sock:
            log.trace(0, 'connection close *%d: %d', self.index, self.sock.fileno())
            if self.rev.active or self.wev.active:
                del_conn(self, WRITE_EVENT | READ_EVENT)
            self.wev.handler = None
            self.rev.handler = None
            self.wev.buff = ''
            self.rev.buff = ''
            close_socket(self.sock)
            self.sock = None

        return self

    def reuse(self):
        s = self.socket()
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception as exc:
            log.error(exc, 'reuse(%d) failed', s.fileno())
            return None

        log.trace(0, 'connection reuse *%d', self.index)
        return self

    def blocking(self):
        s = self.socket()
        try:
            s.setblocking(1)
        except Exception as exc:
            log.error(exc, 'blocking(%d) failed', s.fileno())
            return None

        log.trace(0, 'connection blocking *%d', self.index)
        return self

    def nonblocking(self):
        s = self.socket()
        try:
            s.setblocking(0)
        except Exception as exc:
            log.error(exc, 'nonblocking(%d) failed', s.fileno())
            return None

        log.trace(0, 'connection nonblocking *%d', self.index)
        return self

    def connect(self, addr):
        s = self.socket()
        if not s:
            s = self.socket(addr)
        if not s:
            return None

        try:
            s.connect(addr.sockaddr)
        except Exception as exc:
            err = exc.errno
            if err != errno.EINPROGRESS:
                log.error(exc, 'connect(%s) failed', addr.text)
                return None

        self.addr = addr

        log.trace(0, 'connection connect *%d: %s', self.index, addr.text)
        return self

    def connect_nonblocking(self, addr):
        s = self.socket()
        if not s:
            s = self.socket(addr)
        if not s:
            return None

        if not self.nonblocking():
            return None

        return self.connect(addr)

    def recv(self, size=4096, *args):
        try:
            r = self.socket().recv(size, *args)
            if not r:   # closed
                return 1, r
            return 0, r
        except Exception as exc:
            err = exc.errno
            if err == errno.EAGAIN or err == errno.EINTR:
                return 0, ''
            log.error(exc, 'recv() from %s failed', self.addr.text)
            return -1, -1

    def send(self, buff, *args):
        try:
            r = self.socket().send(buff, *args)
            if not r:   # closed
                return 1, 0
            return 0, r
        except Exception as exc:
            err = exc.errno
            if err == errno.EAGAIN or err == errno.EINTR:
                return 0, 0
            log.error(exc, 'send() to %s failed', self.addr.text)
            return -1, -1
