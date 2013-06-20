all:

check:
	nosetests --with-doctest
	./test.sh
	pep8 http-dbus-bridge.py
