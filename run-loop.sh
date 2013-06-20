#!/bin/sh

./http-dbus-bridge.py "$@" &
HTTPD_PID=$!

inotifywait -m -e CLOSE_WRITE . | grep --line-buffered 'CLOSE_WRITE,CLOSE http-dbus-bridge.py' | while read line
do
	kill "$HTTPD_PID"
	wait "$HTTPD_PID"
	./http-dbus-bridge.py "$@" &
	HTTPD_PID=$!
done
