all: http-dbus-bridge

check:
	nosetests --with-doctest http-dbus-bridge.py \
	          --doctest-options='+NORMALIZE_WHITESPACE,+ELLIPSIS'
	./test.sh
	pep8 http-dbus-bridge.py

#http-dbus-bridge : http-dbus-bridge.vala
#	valac --pkg libsoup-2.4 --pkg json-glib-1.0 --pkg gio-2.0 --enable-checking -o $@ $^
http-dbus-bridge : http-dbus-bridge.vala
	CFLAGS="-Os -m32 -DNDEBUG" valac -X -Os -X -m32 -X -DNDEBUG --pkg libsoup-2.4 --pkg json-glib-1.0 --pkg gio-2.0 -o $@ $^

out/http-dbus-bridge.c : http-dbus-bridge.vala
	mkdir -p out/
	valac --ccode --pkg libsoup-2.4 --pkg json-glib-1.0 --pkg gio-2.0 -d out/ $^

clean:
	-rm -f http-dbus-bridge
