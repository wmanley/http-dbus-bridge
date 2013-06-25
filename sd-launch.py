#!/usr/bin/python
import socket
import os
import sys
import argparse

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('cmd', help='Command to run')
    parser.add_argument('args', nargs='*', help='Command arguments')
    parser.add_argument('--stdout', default='/dev/null',
                        help='File to redirect stdout and stderr to')
    args = parser.parse_args(argv[1:])

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    _, port = s.getsockname()
    s.listen(5)

    pid = os.fork()
    if pid == 0:
        dev_null = os.open('/dev/null', os.O_RDONLY)
        os.dup2(dev_null, 0)
        os.close(dev_null)
        stdout = os.open(args.stdout, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0644)
        os.dup2(stdout, 1)
        os.dup2(stdout, 2)
        os.close(stdout)
        if s.fileno() != 3:
            os.dup2(s.fileno(), 3)
            for fd in range(4, s.fileno() + 1):
                os.close(fd)
        os.execvpe(args.cmd, [args.cmd] + args.args,
                   dict(os.environ.items() + [('LISTEN_PID', str(os.getpid())),
                                              ('LISTEN_FDS', '1')]))
    else:
        sys.stdout.write('LAUNCHED_PORT=%i\nLAUNCHED_PID=%i\n' % (port, pid))
        return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
