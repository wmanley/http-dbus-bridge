all:

check:
	nosetests --with-doctest http-dbus-bridge.py \
	          --doctest-options='+NORMALIZE_WHITESPACE,+ELLIPSIS'
	./test.sh
	pep8 http-dbus-bridge.py
