#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


def call(module_name, function_name, *args, **kargs):
    import importlib

    from core import log

    if isinstance(module_name, str):
        try:
            m = importlib.import_module(module_name)
        except Exception as exc:
            log.error(exc, 'importlib.import_module(%s) failed', module_name)
            return
    else:
        m = module_name
    try:
        f = getattr(m, function_name)
    except Exception as exc:
        log.error(exc, 'getattr(%s, %s) failed', m.__name__, function_name)
        return

    return f(*args, **kargs)

import sys
sys.modules[__name__] = call
