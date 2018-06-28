#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import errno
import socket
import time
import weakref

from core import log
from core.addr import Addr
from core.connection import Connection
from core.connection import is_cygwin


def get_accept_handler(l):
    def event_accept():
        while True:
            if not l.accept():
                return
    return event_accept


class Listening(Connection):
    addr    = None
    backlog = 32
    handler = None

    def __init__(self):
        # super(self.__class__, self).__init__()
        Connection.__init__(self)

        self.rev.handler = self.wev.handler = get_accept_handler(weakref.proxy(self))

    def accept(self):
        try:
            if not is_cygwin:
                s, sockaddr = self.socket().accept()
            else:
                begin = time.time()
                s, sockaddr = self.socket().accept()
                end = time.time()
                if end - begin > 1:
                    log.info(0, 'accept cost %f seconds', end - begin)
                    exit(-1)
        except IOError as exc:
            err = exc.errno
            if err != errno.EAGAIN and err != errno.EINTR:
                log.error(exc, 'accept() fail')
            return None
        except Exception as exc:
            log.error(exc, 'accept() fail')
            return None

        c = Connection()
        c.socket(s)
        c.listening = self
        c.nonblocking()
        c.keepalive()

        c.addr = Addr(self.addr)
        c.addr.parse_sockaddr(sockaddr)

        log.debug(0, '*%d accept: %s', c.index, c.addr.text)
        self.handler(c)

        return self

    def listen(self, addr, backlog = 32):
        if not isinstance(addr, Addr):
            addr = Addr(addr)

        s = self.socket(addr)
        if not s:
            return None

        if not self.reuse():
            self.close()
            return None

        try:
            s.bind(addr.sockaddr)
        except Exception as exc:
            log.error(exc, '*%d bind(%s) fail', self.index, addr.text)
            self.close()
            return None

        try:
            s.listen(backlog)
        except Exception as exc:
            log.error(exc, '*%d listen(%s) fail', self.index, addr.text)
            self.close()
            return None

        log.debug(0, '*%d listen: %s', self.index, addr.text)
        self.nonblocking()
        self.addr = addr
        self.backlog = backlog
        return self
