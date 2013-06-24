#!/usr/bin/env python

import sys
import SimpleHTTPServer
import BaseHTTPServer
import re
import time
import argparse
import json
from itertools import izip, count
from collections import namedtuple
from cStringIO import StringIO
import dbus
import xml.etree.cElementTree as etree

HOST_NAME = '0.0.0.0'


class MyServer(BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, config, conn, allow_introspection):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, MyHandler)
        self.config = config
        self.conn = conn
        self.allow_introspection = allow_introspection


def substitute(result, groups):
    """
    >>> substitute(Result("ab$2", "cd$3fg", "po$2tr", "$1", "$0", "test$3", "he$2l$3lo"), ["a", "b", "c", "d"])
    Result(verb='ab$2', path_regex='cd$3fg', bus_name='poctr', object_path='b', interface='a', method='testd', args='hecldlo')
    """
    full_method = list(result)
    for n, group in reversed(zip(count(), groups)):
        for j in range(2, 7):
            full_method[j] = full_method[j].replace('$%i' % n, group)
    return Result(*full_method)


class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def get_method(self, verb, path):
        for i in self.server.config:
            m = re.match(i.path_regex, self.path)
            if m and i.verb == verb:
                substvars = [self.path] + list(m.groups())
                return (substitute(i, substvars), substvars)
        raise LookupError()

    def respond(self, verb):
        try:
            m, u = self.get_method(verb, self.path)
            #request = json.load(self.rfile)
            c = self.server.conn
            try:
                introspect_file = open('interface-%s.xml' % m.interface, 'r')
            except IOError as e:
                if self.server.allow_introspection:
                    introspect_file = StringIO(c.call_blocking(m.bus_name,
                        m.object_path, 'org.freedesktop.DBus.Introspectable',
                        'Introspect', '', ''))
                else:
                    raise LookupError('Unknown DBus interface \'%s\''
                                      % m.interface)
            xpath = './interface[@name=\'%s\']/method[@name=\'%s\']/arg[@direction=\'in\'][@type]' % (m.interface, m.method)
            signiture = ''.join([x.get('type') for x in etree.parse(introspect_file).findall(xpath)])

            input_data = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            if input_data != "":
                j = json.loads(input_data)
            else:
                j = None
            reply = c.call_blocking(*m[2:6], signature=signiture, args=eval('tuple([%s])' % m.args))
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(reply))
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
        json.dump(exception.message, self.wfile)

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

test_config = """
GET /hello/test/(.*)    org.freedesktop.Notifications   /org/freedesktop/Notifications  org.freedesktop.Notifications.Notify ("", 0, "", "", "", [], {}, 0)
"""


Result = namedtuple('Result', 'verb path_regex bus_name ' +
                              'object_path interface method args')


def parse_config(config):
    """
    >>> list(parse_config(StringIO(test_config)))
    [Result(verb='GET', path_regex='/hello/test/(.*)', bus_name='org.freedesktop.Notifications', object_path='/org/freedesktop/Notifications', interface='org.freedesktop.Notifications', method='Notify', args='"", 0, "", "", "", [], {}, 0')]
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
            sys.stderr.write("Error parsing config file: Could not understand "
                             + "line %i: %s\n" % (line_no, line))


def main(argv):
    parser = argparse.ArgumentParser(description="Make DBus calls based upon HTTP requests")
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--config', type=argparse.FileType('r'), default="config.cfg")
    parser.add_argument('--allow-introspection', type=bool, default=False)
    args = parser.parse_args(argv[1:])

    cfg = parse_config(args.config)
    httpd = MyServer((HOST_NAME, args.port), list(cfg), dbus.SessionBus(),
                     args.allow_introspection)
    print time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    httpd.server_close()
    print time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, args.port)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
