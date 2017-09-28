#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


def closure(data, expression):
    obj = [data]
    def handler():
        tmp = obj[0]
        obj[0] = expression(tmp)
        return tmp
    return handler

class Closure(object):
    def __init__(self, data, expression):
        self.data = data
        self.expr = expression

    def __call__(self):
        data = self.data
        self.data = self.expr(data)
        return data

import sys
sys.modules[__name__] = Closure
