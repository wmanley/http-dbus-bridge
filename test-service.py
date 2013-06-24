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

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface_name):
        print 'return_zero() called'
        return {}

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ss',
                         out_signature='v')
    def Get(self, interface_name, property_name):
        return self.GetAll(interface_name)[property_name]

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s',
                         out_signature='a{sv}')
    def GetAll(self, interface_name):
        if interface_name == 'com.example.service':
            return { 'prop_i': dbus.Int32(1, variant_level=1),
                     'prop_u': dbus.UInt32(1, variant_level=1),
                     'prop_b': dbus.Boolean(True, variant_level=1) }
        else:
            raise dbus.exceptions.DBusException(
                'com.example.UnknownInterface',
                'The Foo object does not implement the %s interface'
                    % interface_name)

    @dbus.service.signal(dbus.PROPERTIES_IFACE,
                         signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties,
                          invalidated_properties):
        pass


DBusGMainLoop(set_as_default=True)
service = TestService()
print "Test service starting up..."
try:
	gtk.main()
finally:
	print "Test service shutting down..."
