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
	while ! dbus-send --print-reply --dest=org.freedesktop.DBus / org.freedesktop.DBus.NameHasOwner string:com.example.service | grep -q true; do
		sleep 0.01
	done

	cat <<-EOF > config.cfg
		GET /example/([A-Za-z0-9_-]+)$ com.example.service /com/example/service com.example.service.\$1 ()
		EOF
	cp $srcdir/interface-com.example.service.xml $srcdir/http-dbus-object-mapping.cfg .
}

launch_bridge() {
	$srcdir/http-dbus-bridge &
	sleep 1
	echo $! > "$scratch_dir/pids/bridge"
	address="localhost:8088"
#	export $($srcdir/sd-launch.py --stdout "$scratch_dir/bridge.log" -- $srcdir/http-dbus-bridge.py "$@")
#	echo $LAUNCHED_PID > "$scratch_dir/pids/bridge"
#	address="localhost:$LAUNCHED_PORT"
}

teardown() {
	cat $scratch_dir/bridge.log
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

test_getting_property() {
	launch_bridge --allow-introspection=true
	[ "$(curl http://$address/example/props/prop_i 2>/dev/null)" = "1" ] ||
		fail "int property not correctly formatted"
	[ "$(curl http://$address/example/props/prop_u 2>/dev/null)" = "1" ] ||
		fail "uint property not correctly formatted"
	[ "$(curl http://$address/example/props/prop_b 2>/dev/null)" = "true" ] ||
		fail "bool property not correctly formatted"
}

test_setting_property() {
	launch_bridge --allow-introspection=true
	curl -fsS -X PUT --data 1 "http://$address/example/props/prop_i" ||
		fail "Failed to set int property"
	curl -fsS -X PUT --data 1 "http://$address/example/props/prop_u" ||
		fail "Failed to set uint property"
	curl -fsS -X PUT --data true "http://$address/example/props/prop_b" ||
		fail "Failed to set boolean property"
}

assert_GET_returns() {
	path=$1
	expected=$2
	data="$(curl -sS http://$address$path)"
	[ "$expected" = "$data" ] || fail "GET $path: Expected '$expected' but received '$data'"
}

test_that_object_path_is_mapped_to_http_endpoint() {
	launch_bridge
	assert_GET_returns "/example/props/prop_o" "\"/example/props\""
}

test_that_unknown_object_path_is_mapped_to_json_null() {
	launch_bridge
	assert_GET_returns "/example/props/prop_unknown_o" "null"
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
