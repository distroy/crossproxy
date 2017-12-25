#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import hashlib


def get_sign(secret, argv):
    buff = []
    for i in argv:
        buff.append(hashlib.md5(secret + str(i)).hexdigest())
    return hashlib.md5(''.join(buff)).hexdigest()
