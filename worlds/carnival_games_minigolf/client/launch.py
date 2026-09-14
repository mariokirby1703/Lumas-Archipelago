import asyncio

import colorama
import Utils
from CommonClient import get_base_parser, handle_url_arg


def launch_client(*args):
    from .client import main

    parser = get_base_parser(description="Carnival Games MiniGolf Archipelago Client")
    parser.add_argument('--name', help='Archipelago slot name')
    parser.add_argument('--local-player', type=int, choices=range(1, 5), default=1,
                        help='Local golfer whose checks and currency belong to this AP slot (default: 1)')
    parser.add_argument('url', nargs='?', help='Archipelago URI or .apcgm output file')
    parsed = parser.parse_args(args)
    parsed.patch_file = None
    if parsed.url and parsed.url.lower().endswith('.apcgm'):
        parsed.patch_file, parsed.url = parsed.url, None
    else:
        parsed = handle_url_arg(parsed, parser=parser)
    colorama.just_fix_windows_console()
    Utils.init_logging('CarnivalGamesMiniGolfClient', exception_logger='Client')
    try:
        asyncio.run(main(parsed))
    finally:
        colorama.deinit()


if __name__ == '__main__':
    import sys
    launch_client(*sys.argv[1:])
