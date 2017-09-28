#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


# import importlib
import weakref

from core import log
from core import call


READ_EVENT = 0x0001
WRITE_EVENT = 0x0002

EVENT_MODULES = {
    'select': ('select_module', 'Select'),
}


class Event(object):

    def __init__(self, c=None):
        self.connection = c

        self.index = None

        self.read = False
        self.write = False
        self.accept = False

        self.active = None
        self.ready = False

        self.handler = None

        self.buff = ''

    def process(self, module=''):
        c = self.connection
        ev = 'read' if self.read else 'write'

        log.trace(0, '[%s] event %s *%d', module, ev, c.index)
        self.ready = True
        self.handler()
        # try:
        #     self.handler()
        # except Exception as exc:
        #     log.error(exc, '*%d process event %s failed', c.index, ev)


_obj = None

def add_conn(c, event, flag=0):
    e = _obj.add_conn(c, event, flag)
    if e:
        log.trace(0, '%s add connection: c:%d ev:%08X', _obj.name, c.index, e)
    return e

def del_conn(c, event, flag=0):
    e = _obj.del_conn(c, event, flag)
    if e:
        log.trace(0, '%s del connection: c:%d ev:%08X', _obj.name, c.index, e)
    return e

def process_events(wait_time=20):
    return _obj.process_events(wait_time)

def init_event(name='select'):
    if name not in EVENT_MODULES:
        return None
    info = EVENT_MODULES[name]
    # m = importlib.import_module('event.modules.' + info[0])
    # f = getattr(m, info[1])
    global _obj
    _obj = call('event.modules.' + info[0], info[1])
    if _obj:
        setattr(_obj, 'name', name)
        log.info(0, 'init event module: %s', name)
    return _obj

def done_event():
    global _obj
    _obj.done()
    _obj = None
