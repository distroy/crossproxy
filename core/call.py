#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


def call(module_name, function_name, *args, **kargs):
    from core import log

    def import_module(module_name):
        arr = module_name.split('.')
        root = arr[0]
        arr = arr[1:]
        try:
            m = __import__(module_name)
        except Exception as exc:
            log.error(exc, '__import__(%s) failed', module_name)
            return

        name = root
        for i in arr:
            try:
                m = getattr(m, i)
                name = '%s.%s' % (name, i)
            except Exception as exc:
                log.error(exc, 'getattr(%s, %s) failed', name, i)
                return
        return m


    if isinstance(module_name, str):
        try:
            m = import_module(module_name)
        except Exception as exc:
            log.error(exc, 'importlib.import_module(%s) failed', module_name)
            return
    else:
        m = module_name

    try:
        f = getattr(m, function_name)
    except Exception as exc:
        log.error(exc, 'getattr(%s, %s) failed', module_name, function_name)
        return

    return f(*args, **kargs)

import sys
sys.modules[__name__] = call
