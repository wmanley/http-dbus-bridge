all:

check:
	nosetests --with-doctest http-dbus-bridge.py
	./test.sh
	pep8 http-dbus-bridge.py
