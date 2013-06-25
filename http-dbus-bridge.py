#!/usr/bin/env python

import sys
import BaseHTTPServer
import re
import time
import os
import argparse
import json
import socket
from itertools import izip, count
from collections import namedtuple
from cStringIO import StringIO
import dbus
import xml.etree.cElementTree as etree

HOST_NAME = '0.0.0.0'


class MyServer(BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, config, conn, allow_introspection,
                 object_mapping, bind_and_activate=True):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, MyHandler,
                                           bind_and_activate=bind_and_activate)
        self.config = config
        self.conn = conn
        self.allow_introspection = allow_introspection
        self.object_mapping = object_mapping


def substitute(result, groups):
    """
    >>> substitute(Result("ab$2", "cd$3fg", "po$2tr", "$1", "$0", "test$3",
    ...                   "he$2l$3lo"), ["a", "b", "c", "d"])
    Result(verb='ab$2', path_regex='cd$3fg', bus_name='poctr', object_path='b',
           interface='a', method='testd', args='hecldlo')
    """
    full_method = list(result)
    for n, group in reversed(zip(count(), groups)):
        for j in range(2, 7):
            full_method[j] = full_method[j].replace('$%i' % n, group)
    return Result(*full_method)


class DBusJSONEncoder(json.JSONEncoder):
    def encode(self, obj):
        if isinstance(obj, dbus.Boolean):
            return 'true' if obj else 'false'
        else:
            return json.JSONEncoder.encode(self, obj)

dbus_types = {
    'b': dbus.Boolean,
    'y': dbus.Byte,
    'n': dbus.Int16,
    'i': dbus.Int32,
    'x': dbus.Int64,
    'q': dbus.UInt16,
    'u': dbus.UInt32,
    't': dbus.UInt64,
    'd': dbus.Double,
    'o': dbus.ObjectPath,
    'g': dbus.Signature,
    's': dbus.String
}


class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def introspect_interface(self, interface, bus_name, object_path):
        c = self.server.conn
        try:
            introspect_file = open('interface-%s.xml' % interface, 'r')
        except IOError as e:
            if self.server.allow_introspection:
                introspect_xml = c.call_blocking(
                    bus_name, object_path,
                    'org.freedesktop.DBus.Introspectable',
                    'Introspect', '', '')
                introspect_file = StringIO(introspect_xml)
            else:
                raise LookupError('Unknown DBus interface \'%s\''
                                  % interface)
        xpath = './interface[@name=\'%s\']' % interface
        return etree.parse(introspect_file).find(xpath)

    def get_mapping(self, path):
        for i in self.server.object_mapping:
            if self.path.startswith(i.http_path):
                return i
        return None

    def respond_properties(self, verb, m, json_in):
        c = self.server.conn
        xml = self.introspect_interface(m.interface, m.bus_name, m.object_path)
        all_properties = xml.findall('property')
        prop_names = [x.get('name') for x in all_properties]
        p = self.path.rstrip('/')
        if verb == 'GET' and p == m.http_path:
            return c.call_blocking(m.bus_name, m.object_path,
                                   'org.freedesktop.DBus.Properties', 'GetAll',
                                   's', (m.interface))
        base, prop = p.rsplit('/', 1)
        # Restrict based upon properties listed in XML for security
        if base == m.http_path and prop in prop_names:
            if verb == 'GET':
                return c.call_blocking(m.bus_name, m.object_path,
                                       'org.freedesktop.DBus.Properties',
                                       'Get', 'ss', (m.interface, prop))
            elif verb == 'PUT':
                t = xml.find('property[@name=\'%s\']' % prop).get('type')
                # TODO: FIXME for complex types:
                v = dbus_types[t](json_in, variant_level=1)
                return c.call_blocking(m.bus_name, m.object_path,
                                       'org.freedesktop.DBus.Properties',
                                       'Set', 'ssv', (m.interface, prop, v))
        raise LookupError('Unknown path \'%s\'' % self.path)

    def get_method(self, verb, path):
        for i in self.server.config:
            m = re.match(i.path_regex, self.path)
            if m and i.verb == verb:
                substvars = [self.path] + list(m.groups())
                return (substitute(i, substvars), substvars)
        return (None, None)

    def respond_commands(self, m, u, j):
        xml = self.introspect_interface(m.interface, m.bus_name,
                                        m.object_path)
        args = xml.findall(
            'method[@name=\'%s\']/arg[@direction=\'in\']' % m.method)
        signiture = ''.join([x.get('type') for x in args])

        return self.server.conn.call_blocking(
            *m[2:6], signature=signiture, args=eval('tuple([%s])' % m.args))

    def respond(self, verb):
        try:
            input_data = self.rfile.read(int(
                self.headers.get('Content-Length', 0)))
            if input_data != "":
                json_in = json.loads(input_data)
            else:
                json_in = None

            m, u = self.get_method(verb, self.path)
            mapping = self.get_mapping(self.path)
            if m is not None:
                reply = self.respond_commands(m, u, json_in)
            elif mapping is not None:
                reply = self.respond_properties(verb, mapping, json_in)
            else:
                raise LookupError('Unknown path \'%s\'' % self.path)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(reply, cls=DBusJSONEncoder))
            self.wfile.write('\n')
        except LookupError as e:
            self.respond_exception(404, e)
        except dbus.DBusException as e:
            self.respond_exception(400, e)
        except Exception as e:
            self.respond_exception(500, e)

    def respond_exception(self, code, exception):
        sys.stderr.write("WARNING: exception thrown: %s\n" % str(exception))
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        json.dump(exception.message, self.wfile, cls=DBusJSONEncoder)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

    def do_GET(self):
        self.respond('GET')

    def do_POST(self):
        self.respond('POST')

    def do_DELETE(self):
        self.respond('DELETE')

    def do_PUT(self):
        self.respond('PUT')

Result = namedtuple('Result', 'verb path_regex bus_name ' +
                              'object_path interface method args')
PathMapping = namedtuple('PathMapping', 'http_path bus_name object_path ' +
                                        'interface type')


def parse_config(config):
    """
    >>> list(parse_config(StringIO(
    ...     'GET /hello/test/(.*)    org.freedesktop.Notifications   ' +
    ...     '/org/freedesktop/Notifications  ' +
    ...     'org.freedesktop.Notifications.Notify ' +
    ...     '("", 0, "", "", "", [], {}, 0)')))
    [Result(verb='GET', path_regex='/hello/test/(.*)',
            bus_name='org.freedesktop.Notifications',
            object_path='/org/freedesktop/Notifications',
            interface='org.freedesktop.Notifications', method='Notify',
            args='"", 0, "", "", "", [], {}, 0')]
    """
    r = re.compile(r'\s*([A-Z]+)\s+(\S+)\s+(\S+)\s+(\S+)\s+' +
                   r'(\S+)\.([\S]+)\s+\((.*)\)')
    for (line_no, line) in izip(count(), iter(config)):
        match = r.match(line)
        if match:
            yield Result(*match.groups())
        elif line.strip() == '' or line.strip()[0] == '#':
            # A comment or blank line
            pass
        else:
            sys.stderr.write("Error parsing config file: Could not " +
                             "understand line %i: %s\n" % (line_no, line))


def parse_path_mapping(config):
    """
    >>> list(parse_path_mapping(StringIO(
    ...     "/my/path My.Bus.Name /my/object/path my.interface.name " +
    ...     "Properties")))
    [PathMapping(http_path='/my/path', bus_name='My.Bus.Name',
                 object_path='/my/object/path', interface='my.interface.name',
                 type='Properties')]
    """
    for (line_no, line) in izip(count(), iter(config)):
        if line.strip() == '' or line.strip()[0] == '#':
            # A comment or blank line
            pass
        elif len(line.split()) == 5:
            yield PathMapping(*line.split())
        else:
            sys.stderr.write("Error parsing config file: Could not " +
                             "understand line %i: %s\n" % (line_no, line))


def main(argv):
    parser = argparse.ArgumentParser(
        description="Make DBus calls based upon HTTP requests")
    parser.add_argument('--port', type=int)
    parser.add_argument('--config', type=argparse.FileType('r'),
                        default="config.cfg")
    parser.add_argument('--allow-introspection', type=bool, default=False)
    args = parser.parse_args(argv[1:])

    cfg = parse_config(args.config)
    object_mapping = list(
        parse_path_mapping(open("http-dbus-object-mapping.cfg", 'r')))
    httpd = MyServer((HOST_NAME, args.port or 8080), list(cfg),
                     dbus.SessionBus(), args.allow_introspection,
                     object_mapping, bind_and_activate=False)
    if (args.port is None and
            os.environ.get('LISTEN_PID', None) == str(os.getpid())):
        assert os.environ['LISTEN_FDS'] == '1'
        httpd.socket = socket.fromfd(3, httpd.address_family,
                                     httpd.socket_type)
    else:
        httpd.server_bind()
    httpd.server_activate()

    print time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    httpd.server_close()
    print time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, args.port)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
