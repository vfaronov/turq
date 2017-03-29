import argparse
import logging
import sys

import turq.mock

DEFAULT_ADDRESS = ''       # All interfaces
DEFAULT_MOCK_PORT = 13085
DEFAULT_RULES = 'error(404)\n'


def main():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s  %(levelname)-8s  %(message)s',
                        datefmt='%H:%M:%S')
    args = parse_args(sys.argv)
    sys.excepthook = excepthook
    run(args)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--bind', metavar='ADDRESS',
                        default=DEFAULT_ADDRESS,
                        help='IP address or hostname to listen on')
    parser.add_argument('-p', '--mock-port', metavar='PORT', type=int,
                        default=DEFAULT_MOCK_PORT,
                        help='port for the mock server to listen on')
    parser.add_argument('-6', '--ipv6', action='store_true',
                        default=False,
                        help='listen on IPv6 instead of IPv4')
    parser.add_argument('-r', '--rules', metavar='PATH',
                        type=argparse.FileType('r'),
                        help='file with initial rules code')
    return parser.parse_args(argv[1:])


def excepthook(_type, exc, _traceback):
    sys.stderr.write('turq: unhandled exception: %r\n' % exc)


def run(args):
    rules = args.rules.read() if args.rules else DEFAULT_RULES
    mock_server = turq.mock.MockServer(args.bind, args.mock_port, args.ipv6,
                                       rules)
    try:
        mock_server.serve_forever()
    except KeyboardInterrupt:
        mock_server.server_close()
        sys.stderr.write('\n')


if __name__ == '__main__':
    main()
