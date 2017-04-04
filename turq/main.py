import argparse
import base64
import logging
import os
import sys
import threading

import colorlog

import turq.editor
import turq.mock
from turq.util.http import guess_external_url

DEFAULT_ADDRESS = ''       # All interfaces
DEFAULT_MOCK_PORT = 13085
DEFAULT_EDITOR_PORT = 13086
DEFAULT_RULES = 'error(404)\n'

logger = logging.getLogger('turq')


def main():
    args = parse_args(sys.argv)
    if not args.verbose:
        sys.excepthook = excepthook
    setup_logging(args)
    run(args)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print more verbose diagnostics')
    parser.add_argument('--no-color', action='store_true',
                        help='do not colorize console output')
    parser.add_argument('--no-editor', action='store_true',
                        help='disable the built-in Web-based rules editor')
    parser.add_argument('-b', '--bind', metavar='ADDRESS',
                        default=DEFAULT_ADDRESS,
                        help='IP address or hostname to listen on')
    parser.add_argument('-p', '--mock-port', metavar='PORT', type=int,
                        default=DEFAULT_MOCK_PORT,
                        help='port for the mock server to listen on')
    parser.add_argument('--editor-port', metavar='PORT', type=int,
                        default=DEFAULT_EDITOR_PORT,
                        help='port for the rules editor to listen on')
    parser.add_argument('-6', '--ipv6', action='store_true',
                        default=False,
                        help=('listen on IPv6 instead of IPv4 '
                              '(or on both, depending on the system)'))
    parser.add_argument('-r', '--rules', metavar='PATH',
                        type=argparse.FileType('r'),
                        help='file with initial rules code')
    parser.add_argument('-P', '--editor-password', metavar='PASSWORD',
                        default=random_password(),
                        help='explicitly set editor password '
                             '(empty string to disable)')
    return parser.parse_args(argv[1:])


def excepthook(_type, exc, _traceback):
    sys.stderr.write('turq: error: %s\n' % exc)


def setup_logging(args):
    if args.no_color:
        formatter = logging.Formatter(
            fmt='%(asctime)s  %(name)s  %(message)s',
            datefmt='%H:%M:%S')
    else:
        formatter = colorlog.ColoredFormatter(
            fmt=('%(asctime)s  '
                 '%(name_log_color)s%(name)s%(reset)s  '
                 '%(log_color)s%(message)s%(reset)s'),
            datefmt='%H:%M:%S',
            log_colors={'DEBUG': 'green', 'ERROR': 'red', 'CRITICAL': 'red'},
            secondary_log_colors={
                'name': {'DEBUG': 'cyan', 'INFO': 'cyan',
                         'WARNING': 'cyan', 'ERROR': 'cyan',
                         'CRITICAL': 'cyan'},
            },
        )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)


def run(args):
    rules = args.rules.read() if args.rules else DEFAULT_RULES
    mock_server = turq.mock.MockServer(args.bind, args.mock_port, args.ipv6,
                                       rules)

    if args.no_editor:
        editor_server = None
    else:
        editor_server = turq.editor.make_server(
            args.bind, args.editor_port, args.ipv6,
            args.editor_password, mock_server)
        threading.Thread(target=editor_server.serve_forever).start()

    # Show mock server info just before going into `serve_forever`,
    # to minimize the delay between printing it and actually listening
    show_server_info('mock', mock_server)
    if editor_server is not None:
        show_server_info('editor', editor_server)
        if args.editor_password:
            logger.info('editor password: %s (any username)',
                        args.editor_password)

    try:
        mock_server.serve_forever()
    except KeyboardInterrupt:
        mock_server.server_close()
        sys.stderr.write('\n')

    if editor_server is not None:
        editor_server.shutdown()
        editor_server.server_close()


def show_server_info(label, server):
    (host, port, *_) = server.server_address
    logger.info('%s on port %d - try %s',
                label, port, guess_external_url(host, port))


def random_password():
    return base64.b64encode(os.urandom(18), altchars=b'Ab').decode()


if __name__ == '__main__':
    main()
