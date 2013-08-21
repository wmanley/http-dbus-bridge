using Soup;
using Json;

struct PathMapping {
    public string http_path;
    public string bus_name;
    public string object_path;
    RequestHandler handler;
}

class RequestHandler : GLib.Object {
    public virtual async void handle(PathMapping mapping, DBusConnection bus, Soup.Server server,
                  Soup.Message msg, string path,
                  GLib.HashTable<string, string>? query,
                  Soup.ClientContext client)
    {
    }
}

class PropertiesRequestHandler : RequestHandler {
    private string dbus_interface;
    private DBusInterfaceInfo interface_info;
    public PropertiesRequestHandler(string dbus_interface_, DBusInterfaceInfo interface_info_)
    {
        this.dbus_interface = dbus_interface_;
        this.interface_info = interface_info_;
    }
    public override async void handle(PathMapping mapping, DBusConnection bus, Soup.Server server,
                  Soup.Message msg, string path,
                  GLib.HashTable<string, string>? query,
                  Soup.ClientContext client)
    {
        var property_name = path.substring(mapping.http_path.length).replace("/", " ").strip();
        try {
            if (msg.method == "GET" && property_name.length == 0) {
                server.pause_message(msg);
                var response = yield bus.call(
                    mapping.bus_name, mapping.object_path,
                    "org.freedesktop.DBus.Properties", "GetAll",
                    new Variant("(s)", this.dbus_interface),
                    new VariantType("(a{sv})"), DBusCallFlags.NONE, -1);
                msg.set_response ("application/json", Soup.MemoryUse.COPY, Json.gvariant_serialize_data(response, null).data);
                msg.set_status(200);
            }
            else if (property_name.length > 0) {
                var p = this.interface_info.lookup_property(property_name);
                if (p == null) {
                    msg.set_status(404);
                }
                else if (msg.method == "PUT") {
                    var input = Json.gvariant_deserialize_data((string) msg.request_body.data, -1, p.signature);
                    server.pause_message(msg);
                    var response = yield bus.call(
                        mapping.bus_name, mapping.object_path,
                        "org.freedesktop.DBus.Properties", "Set",
                        new Variant("(ssv)", this.dbus_interface, property_name, input),
                        new VariantType("()"), DBusCallFlags.NONE, -1);
                    msg.set_response ("application/json", Soup.MemoryUse.COPY, Json.gvariant_serialize_data(response, null).data);
                    msg.set_status(200);
                }
                else if (msg.method == "GET") {
                    server.pause_message(msg);
                    var response = yield bus.call(
                        mapping.bus_name, mapping.object_path,
                        "org.freedesktop.DBus.Properties", "Get",
                        new Variant("(ss)", this.dbus_interface, property_name),
                        new VariantType("(v)"), DBusCallFlags.NONE, -1);
                    msg.set_response ("application/json", Soup.MemoryUse.COPY,
                                      Json.gvariant_serialize_data(response.get_child_value(0), null).data);
                    msg.set_status(200);
                }
                else {
                    msg.set_status(400);
                }
            }
            else {
                msg.set_status(400);
            }
        } catch {
            msg.set_response ("text/plain", Soup.MemoryUse.COPY,
                              "Error".data);
            msg.set_status(400);
        } finally {
            server.unpause_message(msg);
        }
    }
}

List<PathMapping?> parse_config_file(DataInputStream i) throws Error
{
    var ret = new List<PathMapping?>();
    var properties_regex = new Regex ("Properties\\(interface=(.*)\\)");
    var line = "";
    while ((line = i.read_line()) != null) {
        if (line.strip() == "" || line.strip()[0] == '#') {
            /* pass */
        }
        else {
            var v = Regex.split_simple("\\s+", line);
            GLib.MatchInfo info;
            properties_regex.match (v[3], 0, out info);
            var interface_name = info.fetch(1);

            uint8[] xml = new uint8[4096];
            size_t bytes_read;
            var input = new DataInputStream (File.new_for_path ("interface-" + interface_name + ".xml").read ());
            if (!input.read_all(xml, out bytes_read)) {
                stderr.printf("Couldn't load introspection xml\n");
                continue;
            }
            var nodeinfo = new DBusNodeInfo.for_xml((string) xml);
            var interface_info = nodeinfo.lookup_interface(interface_name);

            ret.append( {v[0], v[1], v[2], new PropertiesRequestHandler(interface_name, interface_info) });
        }
    }
    return ret;
}

class Demo.HelloWorld : GLib.Object {

    public static int main(string[] args) {
        try {
            var config = File.new_for_path("http-dbus-object-mapping.cfg");
            var config_stream = new DataInputStream (config.read());
            var cfg = parse_config_file(config_stream);

            var bus = Bus.get_sync(BusType.SESSION);
            var server = new Soup.Server(Soup.SERVER_PORT, 8088);

            server.add_handler("/", (server, msg, path, query, client) => {
                foreach (var i in cfg) {
                    /* TODO: Add pattern matching */
                    if (path.has_prefix(i.http_path)) {
                        i.handler.handle.begin (i, bus, server, msg, path, query, client);
                        return;
                    }
                }
                msg.set_status(404);
            });
            server.run();
            stdout.printf("Hello, World\n");

            return 0;
        } catch (Error e) {
            stderr.printf("Oh noes, it went wrong: %s\n", e.message);
            return 1;
        }
    }
}

