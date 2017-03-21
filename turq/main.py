import argparse
import logging
import sys


DEFAULT_RULES = 'error(404)\n'


def main():
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s  %(levelname)-8s  %(message)s',
                        datefmt='%H:%M:%S')
    args = parse_args(sys.argv)
    if not args.full_traceback:
        sys.excepthook = excepthook
    run(args)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--full-traceback', action='store_true',
                        help='do not hide the traceback on exceptions')
    parser.add_argument('-r', '--rules', metavar='PATH',
                        type=argparse.FileType('r'),
                        help='file with initial rules code')
    return parser.parse_args(argv[1:])


def excepthook(_type, exc, _traceback):
    sys.stderr.write('turq: unhandled exception: %r\n' % exc)


def run(args):
    rules = args.rules.read() if args.rules else DEFAULT_RULES
    print(rules)


if __name__ == '__main__':
    main()
