#!/bin/sh

./http-dbus-bridge.py "$@" &
HTTPD_PID=$!

inotifywait -m -e CLOSE_WRITE . | grep -E --line-buffered 'CLOSE_WRITE,CLOSE (http-dbus-bridge.py|config.cfg|http-dbus-object-mapping.cfg)' | while read line
do
	kill "$HTTPD_PID"
	wait "$HTTPD_PID"
	./http-dbus-bridge.py "$@" &
	HTTPD_PID=$!
done
