#! /usr/bin/env bash
#
# Copyright (C) distroy
#


# cd "$(dirname "$BASH_SOURCE")"

CP0=cp0
CP1=cp1
CP2=cp2

EXEC_CP0=./$CP0
EXEC_CP1=./$CP1
EXEC_CP2=./$CP2

function start_cp0() {
    local listen="$1"
    $EXEC_CP0 -l "$listen" &> /dev/null
}

function start_cp1() {
    local key="$1"
    local secret="$2"
    local proxy="$3"
    local target="$4"
    if [[ "$target" == "" ]]; then
        local target='127.0.0.1:22'
    fi
    local num=$(ps f -fj -e | grep -w $CP1 | grep "$proxy" | grep -w "$key" | grep -v grep | wc -l)
    if (( num == 0 )); then
        # echo $EXEC_CP1 -k "$key" -s "$secret" -p "$proxy" -t "$target"
        $EXEC_CP1 -k "$key" -s "$secret" -p "$proxy" -t "$target"
    fi
}

function start_cp2() {
    local key="$1"
    local secret="$2"
    local proxy="$3"
    local listen="$4"
    # echo $EXEC_CP2 -k "$key" -s "$secret" -p "$proxy" -l "$listen"
    $EXEC_CP2 -k "$key" -s "$secret" -p "$proxy" -l "$listen" &> /dev/null
}
