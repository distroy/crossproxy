#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) distroy
#


import inspect
import os
import sys
import time


WORK_PATH = ''


class Color(object):
    '''
        格式：\033[显示方式;前景色;背景色m

        说明：
        前景色            背景色           颜色
        ---------------------------------------
        30                40              黑色
        31                41              红色
        32                42              绿色
        33                43              黃色
        34                44              蓝色
        35                45              紫红色
        36                46              青蓝色
        37                47              白色
        显示方式           意义
        -------------------------
        0                终端默认设置
        1                高亮显示
        4                使用下划线
        5                闪烁
        7                反白显示
        8                不可见
    '''
    RESET = '\033[0m'
    FG_R = '\033[1;31m'  # red
    FG_G = '\033[1;32m'  # green
    FG_Y = '\033[1;33m'  # yellow
    FG_B = '\033[1;34m'  # blue
    FG_M = '\033[1;35m'  # magenta 紫红色
    FG_C = '\033[1;36m'  # cyan 青蓝色
    FG_W = '\033[1;37m'  # white


LVL_ALERT = 0x0000
LVL_ERROR = 0x0001
LVL_WARN = 0x0002
LVL_INFO = 0x0003
LVL_DEBUG = 0x0004
LVL_TRACE = 0x0005

LVL_ALL = 0x7fffffff
LVL_DEFAULT = LVL_DEBUG


_lvl_infos = [
    {
        'name': 'ALERT',
        'color': '\033[1;37;41m',
    }, {
        'name': 'ERROR',
        'color': Color.FG_R,
    }, {
        'name': 'WARN',
        'color': Color.FG_Y,
    }, {
        'name': 'INFO',
        'color': Color.FG_C,
    }, {
        'name': 'DEBUG',
        'color': Color.FG_G,
    }, {
        'name': 'TRACE',
        'color': '',
    },
]

_lvl_map = {}
for i in range(len(_lvl_infos)):
    _lvl_map[_lvl_infos[i]['name'].lower()] = i
_lvl_map.update({
    'all':      LVL_ALL,
    'default':  LVL_DEFAULT,
})


class Log(object):
    __fd = -1
    __level = LVL_DEFAULT
    _prog = ''
    _use_stderr = True
    _show_pid = True
    _prog = ''
    _path = ''
    _name = ''
    _full_path = ''
    _file_limit = 100 << 20

    def __init__(self):
        self._prog = os.path.basename(sys.argv[0])

    def __del__(self):
        self.done()

    def set_work_path(self, path):
        global WORK_PATH
        WORK_PATH = os.path.abspath(path)

    def init(self, path='', name=''):
        if path != '' and name != '':
            path = os.path.abspath(path)
            if not os.path.exists(path):
                os.makedirs(path, 0777)
            self._path = path
            self._name = name
            self._full_path = os.path.join(path, '%s.log' % name)
            self.__open_file()

        self.__class__._show_pid = True
        self.trace(0, 'init log: %s', path)

    def done(self):
        if self.__fd != -1:
            os.close(self.__fd)
            self.__fd = -1

    def __open_file(self):
        if not self._full_path:
            return

        if self.get_file_size() > self._file_limit:
            if self.__fd != -1:
                os.close(self.__fd)
                self.__fd = -1

        path = self._full_path
        if os.path.exists(path) and os.path.getsize(path) > self._file_limit:
            try:
                os.rename(path, path + '.1')
            except Exception as exc:
                self.__error_core_print(lvl=LVL_ERROR, depth=1, exc=0,
                                        fmt='os.rename() fail', args=[])

        if self.__fd == -1:
            flag = os.O_CREAT | os.O_RDWR | os.O_APPEND | os.O_SYNC
            self.__fd = os.open(path, flag, 0644)

    def get_file_size(self):
        if self.__fd == -1:
            return 0
        try:
            stat = os.fstat(self.__fd)
        except Exception as exc:
            self.__error_core_print(lvl=LVL_ERROR, depth=1, exc=0,
                                    fmt='os.fstat() fail', args=[])
            return 0
        if stat.st_nlink > 0:
            return stat.st_size
        return 0xffffffff

    def __to_level(self, lvl):
        try:
            return int(lvl)
        except:
            pass

        try:
            lvl = lvl.lower()
            lvl = _lvl_map[lvl]
            return lvl
        except:
            pass

        return -1

    def set_level(self, lvl):
        l = self.__to_level(lvl)
        if l < 0:
            return -1

        self.__level = l
        return 0

    def set_proc(self, prog):
        self._proc_name = prog

    def dup_stderr(self):
        if self.__fd != -1:
            os.dup2(self.__fd, sys.stderr.fileno())
            self.__class__._use_stderr = False

    def __call_info(self, depth):
        depth += 1
        stack = inspect.stack()
        if depth < 0:
            depth = 0
        elif depth >= len(stack):
            depth = len(stack) - 1

        frame = stack[depth]
        info = self.__stack_frame(frame)
        return '@{function} {file}:{lineno}'.format(**info)

    def __call_stack(self, depth):
        depth += 1
        stack = inspect.stack()
        if depth > 0 and depth < len(stack) - 1:
            stack = stack[depth:]

        buff = []
        for frame in stack:
            info = self.__stack_frame(frame)
            buff.append('{file}:{lineno} {function}'.format(**info))

        return '\n'.join(buff)

    def __stack_frame(self, frame):
        file_path = os.path.abspath(frame[1])
        rel_path = os.path.relpath(file_path, WORK_PATH)
        if not rel_path.startswith('..'):
            file_path = rel_path

        cls_name = ''
        fn_name = frame[3]
        fn_args = inspect.getargvalues(frame[0]).args
        if len(fn_args) > 0 and fn_args[0] == 'self':
            cls_name = frame[0].f_locals['self'].__class__.__name__
            fn_name = '.'.join([cls_name, fn_name])
            fn_args = fn_args[1:]

        code_list = frame[4]  # eg: ['    A().test()\n']

        return {
            'file': file_path,
            'lineno': frame[2],
            'function': '%s(%s)' % (fn_name, ', '.join(fn_args)),
            'class': cls_name,
            'fn_name': fn_name,
            'fn_args': fn_args,
            'code_list': code_list,
        }

    def __lvl_handler(self, lvl):
        if lvl > self.__level:
            return lambda *args: None
        return lambda exc, fmt, *args: self.__error_core(lvl=lvl, depth=2, exc=exc, fmt=fmt, args=args)

    def alert(self, exc, fmt, *args):
        return self.__lvl_handler(LVL_ALERT)(exc, fmt, *args)

    def error(self, exc, fmt, *args):
        return self.__lvl_handler(LVL_ERROR)(exc, fmt, *args)

    def warn(self, exc, fmt, *args):
        return self.__lvl_handler(LVL_WARN)(exc, fmt, *args)

    def info(self, exc, fmt, *args):
        return self.__lvl_handler(LVL_INFO)(exc, fmt, *args)

    def debug(self, exc, fmt, *args):
        return self.__lvl_handler(LVL_DEBUG)(exc, fmt, *args)

    def trace(self, exc, fmt, *args):
        return self.__lvl_handler(LVL_TRACE)(exc, fmt, *args)

    def traceback(self):
        return self.__lvl_handler(LVL_TRACE)(0, 'traceback:\n%s', self.__call_stack(1))

    def try_call(self, handler, fmt, *args):
        try:
            return handler()
        except Exception as exc:
            import traceback
            exc_msg = traceback.format_exc()
            self.__lvl_handler(LVL_ERROR)(0, '\n%s', exc_msg)
            return None

    def core_debug(self, lvl, exc, fmt, *args):
        if lvl & self.__level:
            return self.__error_core(lvl=LVL_DEBUG, depth=1, exc=exc, fmt=fmt, args=args)

    def core_error(self, lvl, exc, fmt, *args):
        return self.__error_core(lvl=lvl, depth=1, exc=exc, fmt=fmt, args=args)

    def __error_core(self, lvl=0, depth=0, exc=0, fmt='', args=[]):
        self.__open_file()
        self.__error_core_print(lvl, depth + 1, exc, fmt, args)

    def __error_core_print(self, lvl=0, depth=0, exc=0, fmt='', args=[]):
        fd = self.__fd
        buff = []

        if lvl < 0:
            lvl = 0
        elif lvl >= len(_lvl_infos):
            lvl = len(_lvl_infos) - 1
        log_info = _lvl_infos[lvl]

        buff.append(time.strftime('%Y-%m-%d %H:%M:%S'))
        buff.append(' ')
        # buff.append('[')
        buff.append(log_info['name'])
        # buff.append(']')

        if self._show_pid and self._prog:
            buff.append(' ')
            buff.append('%s:%d#%d' % (self._prog, os.getpid(), 0))
        elif self._show_pid:
            buff.append(' ')
            buff.append('%d#%d' % (os.getpid(), 0))

        buff.append(' ')
        buff.append(log_info['color'])
        if len(args) == 0:
            buff.append(fmt)
        else:
            buff.append(fmt % tuple(args))

        if exc != 0:
            buff.append(' ')
            buff.append(self.__exception_info(exc))
        buff.append(Color.RESET)

        if depth > 0:
            buff.append(' ')
            buff.append(self.__call_info(depth + 1))

        buff.append('\n')

        s = ''.join(buff)
        if fd != -1:
            os.write(fd, s)

        if self._use_stderr:
            sys.stderr.write(s)

    def __exception_info(self, exc):
        try:
            return '(%s)' % str(exc)
        except:
            return '(unknown exception: %s)' % (exc.__class__.__name__)


def _init():
    log = Log()
    module = sys.modules[__name__]
    for attr in dir(log):
        if attr[1] == '_':
            continue
        setattr(module, attr, getattr(log, attr))

    l = 0
    for info in _lvl_infos:
        if l < len(info['name']):
            l = len(info['name'])
    for info in _lvl_infos:
        info['name'] = info['name'].rjust(l)


_init()
del _init
