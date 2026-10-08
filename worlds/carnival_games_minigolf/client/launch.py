import asyncio
import logging
import sys

import colorama
from CommonClient import get_base_parser, handle_url_arg


def init_console_logging():
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.INFO)
    if sys.stdout is None:
        handler = logging.NullHandler()
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    root.addHandler(handler)


def launch_client(*args):
    from .client import main

    parser = get_base_parser(description="Carnival Games MiniGolf Archipelago Client")
    parser.add_argument('--name', help='Archipelago slot name')
    parser.add_argument('--local-player', type=int, choices=(1,), default=1,
                        help='Local golfer whose checks and currency belong to this AP slot (default: 1)')
    parser.add_argument('url', nargs='?', help='Archipelago URI or .apcgm output file')
    parsed = parser.parse_args(args)
    parsed.patch_file = None
    if parsed.url and parsed.url.lower().endswith('.apcgm'):
        parsed.patch_file, parsed.url = parsed.url, None
    else:
        parsed = handle_url_arg(parsed, parser=parser)
    colorama.just_fix_windows_console()
    init_console_logging()
    try:
        asyncio.run(main(parsed))
    finally:
        colorama.deinit()


if __name__ == '__main__':
    import sys
    launch_client(*sys.argv[1:])
