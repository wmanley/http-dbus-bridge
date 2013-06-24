#!/usr/bin/python -u

import gtk
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

class TestService(dbus.service.Object):
    def __init__(self):
        bus_name = dbus.service.BusName('com.example.service', bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, '/com/example/service')

    @dbus.service.method('com.example.service', in_signature='',
                         out_signature='')
    def print0(self):
        print 'print0 called'

    @dbus.service.method('com.example.service', in_signature='s',
                         out_signature='')
    def print_string(self, string):
        print 'print_string(%s) called' % string

    @dbus.service.method('com.example.service', in_signature='',
                         out_signature='i')
    def return_zero(self):
        print 'return_zero() called'
        return 0

DBusGMainLoop(set_as_default=True)
service = TestService()
print "Test service starting up..."
try:
	gtk.main()
finally:
	print "Test service shutting down..."
