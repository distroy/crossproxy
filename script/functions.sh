#! /usr/bin/env bash
#
# Copyright (C) distroy
#


# cd "$(dirname "$BASH_SOURCE")"

CP0=cp0
CP1=cp1
CP2=cp2

function start_cp0() {
    local listen="$1"
    ./$CP0 -l "$listen" &> /dev/null
}

function start_cp1() {
    local key="$1"
    local proxy="$2"
    local target="$3"
    if [[ "$target" == "" ]]; then
        local target='127.0.0.1:22'
    fi
    local num=$(ps f -fj -e | grep -w $CP1 | grep "$proxy" | grep -w "$key" | grep -v grep | wc -l)
    if (( num == 0 )); then
        ./$CP1 -k "$key" -p "$proxy" -t "$target"
    fi
}

function start_cp2() {
    local key="$1"
    local proxy="$2"
    local listen="$3"
    ./$CP2 -k "$key" -p "$proxy" -l "$listen" &> /dev/null
}
