#!/bin/bash -e

srcdir=$(dirname $(readlink -f $0))

setup() {
	child_pids=""
	scratch_dir=$(mktemp -d)
	cd "$scratch_dir"
	mkdir pids
	export $(dbus-launch)
	echo $DBUS_SESSION_BUS_PID > pids/dbus
	cp "$srcdir/config.cfg" .

	$srcdir/test-service.py > test-service.log &
	echo $! > pids/test-service

	cat <<-EOF > config.cfg
		GET /example/(.+) com.example.service /com/example/service com.example.service.\$1 ()
		EOF
	cp $srcdir/interface-com.example.service.xml .
}

launch_bridge() {
	# FIXME: This is not a robust way of selecting a port that is not in use.
	# Use systemd-style activation.
	port=$(expr $RANDOM + 1024)
	$srcdir/http-dbus-bridge.py --port "$port" "$@" &
	echo $! > "$scratch_dir/pids/bridge"
	address="localhost:$port"

	# TODO: Robustly wait until everything's setup
	sleep 1
}

teardown() {
	kill $(cat $scratch_dir/pids/*) &>/dev/null
	cd "$srcdir"
	rm -Rf "$scratch_dir"
}

fail() {
	printf "ERROR: %s\n" "$1" 1>&2
	exit 1
}

test_that_we_receive_404_on_unknown_path() {
	launch_bridge
	curl -D /dev/stdout http://$address/unknown 2>/dev/null | grep -q "404" || fail ""
}

test_that_dbus_call_is_made_in_response_to_http_get() {
	launch_bridge
	curl -D /dev/stdout http://$address/example/print0 2>/dev/null | grep -q "200" || fail ""
	grep -q 'print0 called' "test-service.log" || fail "No method call made"
}

test_that_we_receive_404_if_static_introspection_xml_is_not_available() {
	rm interface-com.example.service.xml
	launch_bridge
	curl -D /dev/stdout http://$address/example/print0 2>/dev/null | grep -q "404" || fail ""
}

test_success_if_static_introspection_xml_is_not_available_but_introspection_enabled() {
	rm interface-com.example.service.xml
	launch_bridge --allow-introspection=true
	curl -D /dev/stdout http://$address/example/print0 2>/dev/null | grep -q "200" || fail ""
}

test_success_if_static_introspection_xml_is_available() {
	launch_bridge
	curl -D /dev/stdout http://$address/example/print0 2>/dev/null | grep -q "200" || fail ""
}

failures=0
tests=${*:-$(declare -F | awk '/ test_/ {print $3}')}
for t in $tests; do
	printf "Running test '%s'..." "$t"
	( # subshells for robustness
		setup
		( $t; ) && status=0 || status=1
		teardown
		exit $status
	) &> test-run.log && status=0 || status=1
	if [ "$status" -eq 0 ]; then
		printf 'OK\n';
	else
		failures="$(expr $failures + 1)"
		printf 'FAIL.  log output:\n'
		cat test-run.log
	fi
done

exit $failures
