http-dbus-bridge
================

A proof of concept implementation of providing a REST like API as a bridge to
DBus services.  A mapping between the HTTP paths and and DBus methods can be
configured by editing `config.cfg`.

Warning: This is purely a proof of concept and is a **massive security hole**.  Do
not use.

Example:
--------

With the default configuration file included the following will make a desktop
notification appear as a result of an HTTP request:

    $ ./http-dbus-bridge.py --port 8081 &
    $ cat <<EOF | curl --data-binary @- 'http://localhost:8081/notify' 2>/dev/null
    {
        "title": "hello",
        "message": "goodbye"
    }
    EOF

And the following will retrieve the properties of your gnome shell session as
JSON:

    $ ./http-dbus-bridge.py --port 8081 &
    $ curl 'http://localhost:8081/shell' 2>/dev/null
    {"OverviewActive": 0, "ShellVersion": "3.4.2", "ApiVersion": 1}

With this retrieving a single one of these properties:

    $ ./http-dbus-bridge.py --port 8081 &
    $ curl 'http://localhost:8081/shell/ShellVersion' 2>/dev/null
    "3.4.2"

Licence:
--------

This project is free software and may be used and distributed under the terms
of the [GNU General Public Licence V2](http://www.gnu.org/licenses/gpl-2.0.html)
or at your option any later version.

Contact
-------

This project can be found on github at
http://github.com/wmanley/http-dbus-bridge.  See `COPYING` for details.

Thanks
------

Thanks to John Sadler for the idea.
