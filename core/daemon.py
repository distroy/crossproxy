#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import os
import sys
import time
import atexit
import signal

from core import log


def daemon():
    pid = os.fork()
    if pid != 0:
        exit(0)

    os.setsid()

    fd = os.open('/dev/null', os.O_RDWR)
    os.dup2(fd, sys.stdin.fileno())
    os.dup2(fd, sys.stdout.fileno())
    os.dup2(fd, sys.stderr.fileno())

    os.close(fd)
    log.info(0, 'daemon process run')

def process(child_run):
    while True:
        pid = os.fork()
        if pid == 0:  # child
            atexit.register(log.info, 0, 'process exit')
            signal.signal(signal.SIGTERM, lambda sig, stack: exit(0))
            child_run()
            return

        pid, status = os.waitpid(pid, 0)
        log.warn(0, 'child:%d exit with code: %d', pid, status)
        if status != 0:
            time.sleep(1)

        log.info(0, 'reboot process')
