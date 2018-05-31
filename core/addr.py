#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import socket

from core import log


class Addr(object):
    addr_infos = None
    info_index = 0

    text = ''
    addr_text = ''
    sockaddr = None

    family = 0
    socktype = 0
    proto = 0

    def __init__(self, addr='', *args):
        if not addr:
            return

        self.parse(addr, *args)

    def set_tcp(self):
        self.__set_procotol(socket.AF_INET, socket.SOCK_STREAM, socket.SOL_TCP)

    def __set_procotol(self, family=0, socktype=0, proto=0):
        if not family:
            family = socket.AF_INET
        if not socktype:
            socktype = socket.SOCK_STREAM
        if not proto:
            proto = 0

        self.family = family
        self.socktype = socktype
        self.proto = proto

    def __set_addr_text(self):
        self.addr_text = ':'.join([str(i) for i in self.sockaddr])

    def is_valid(self):
        return self.sockaddr != None

    def parse(self, addr, *args):
        if isinstance(addr, Addr):
            self.text = addr.text
            self.addr_text = addr.addr_text
            self.sockaddr = addr.sockaddr
            self.__set_procotol(addr.family, addr.socktype, addr.proto)
            return self

        elif isinstance(addr, tuple) or isinstance(addr, list):
            return self.parse_sockaddr(addr)

        return self.parse_text(str(addr), *args)

    # text [, family, socktype, proto, flags]
    def parse_text(self, text, *args):
        self.text = text
        self.sockaddr = None

        arr = text.split(':')
        if len(arr) != 2:
            log.error(0, 'invalid addr text: %s', text)
            return None

        try:
            addr_infos = socket.getaddrinfo(arr[0], arr[1], *args)
        except Exception as exc:
            log.error(exc, 'socket.getaddrinfo(%s) fail', text)
            return None
        if not addr_infos:
            log.error(0, 'socket.getaddrinfo(%s) is empty', text)
            return None

        self.addr_infos = addr_infos
        log.trace(0, 'socket.getaddrinfo(%s): %r', text, addr_infos)

        self.__set_addr_info(0)
        log.trace(0, 'Addr.parse_text(%s): %s', text, self.sockaddr)
        return self

    def __set_addr_info(self, index):
        if not self.addr_infos or index >= len(self.addr_infos):
            return None

        self.info_index = index
        # addr info: (family, socktype, proto, canonname, sockaddr)
        info = self.addr_infos[index]
        log.trace(0, 'text: %s, index: %d, addr info: %r', self.text, index, info)

        self.__set_procotol(info[0], info[1], info[2])
        self.sockaddr = info[4]
        self.__set_addr_text()
        return self

    def next_sockaddr(self):
        index = self.info_index + 1
        if not self.__set_addr_info(index):
            return None
        log.trace(0, 'Addr.next_sockaddr(): %s', self.sockaddr)
        return self

    def parse_sockaddr(self, sockaddr):
        self.sockaddr = sockaddr
        if isinstance(sockaddr, tuple) or isinstance(sockaddr, list):
            self.text = ':'.join([str(i) for i in sockaddr])
        else:
            self.text = str(sockaddr)

        self.addr_text = self.text
        log.trace(0, 'Addr.parse_sockaddr() result: %s', self.sockaddr)
        return self

    def parse_listening(self, text):
        arr = text.split(':')
        if len(arr) == 1:
            arr.insert(0, '0.0.0.0')

        if len(arr) != 2:
            log.error(0, 'invalid addr text: %s', text)
            return None

        return self.parse_text(':'.join(arr))

    def parse_http(self, text):
        arr = text.split(':')
        if len(arr) == 1:
            arr.append('80')

        if len(arr) != 2:
            log.error(0, 'invalid addr text: %s', text)
            return None

        return self.parse_text(':'.join(arr))
