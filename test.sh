#!/bin/bash

setup() {
	export $(dbus-launch)
	./http-dbus-bridge.py --port 8082 "$@" &
	# TODO: Robustly wait until we're listening
	sleep 1
	BRIDGE_PID=$!
}

teardown() {
	kill "$BRIDGE_PID" "$DBUS_SESSION_BUS_PID"
}

fail() {
	printf "ERROR: %s\n" "$1" 1>&2
	teardown
	exit 1
}

setup
curl -D /dev/stdout http://localhost:8082/unknown 2>/dev/null | grep -q "404" || fail ""
teardown

exit 0
