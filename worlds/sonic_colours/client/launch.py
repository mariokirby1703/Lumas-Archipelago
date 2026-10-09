import asyncio
import logging
import sys
from CommonClient import get_base_parser, handle_url_arg


def launch_client(*args):
    from .client import main
    parser = get_base_parser(description='Sonic Colours PAL Archipelago Client (research build)')
    parser.add_argument('--name', help='Archipelago slot name')
    parser.add_argument('url', nargs='?', help='archipelago:// URI or .apsonic file')
    parsed = parser.parse_args(args)
    parsed.patch_file = None
    if parsed.url and parsed.url.lower().endswith('.apsonic'):
        parsed.patch_file, parsed.url = parsed.url, None
    else:
        parsed = handle_url_arg(parsed, parser=parser)
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
    asyncio.run(main(parsed))


if __name__ == '__main__':
    launch_client(*sys.argv[1:])
