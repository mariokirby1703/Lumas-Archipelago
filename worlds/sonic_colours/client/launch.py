import asyncio
import logging
import sys
from CommonClient import get_base_parser, handle_url_arg


def launch_client(*args):
    from .client import main
    parser = get_base_parser(description='Sonic Colours PAL Archipelago Client (research build)')
    parser.add_argument('--name', help='Archipelago slot name')
    parser.add_argument('--patch-music', nargs=2, metavar=('ORIGINAL_CPK', 'OUTPUT_CPK'),
                        help='Build a separate seed music CPK from the .apsonic file, then exit')
    parser.add_argument('url', nargs='?', help='archipelago:// URI or .apsonic file')
    parsed = parser.parse_args(args)
    parsed.patch_file = None
    if parsed.url and parsed.url.lower().endswith('.apsonic'):
        parsed.patch_file, parsed.url = parsed.url, None
    else:
        parsed = handle_url_arg(parsed, parser=parser)
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
    if parsed.patch_music:
        if not parsed.patch_file:
            parser.error('--patch-music requires a generated .apsonic file')
        import json
        from pathlib import Path
        from .runtime import validate_slot
        from .asset_patch import patch_music
        slot = validate_slot(json.loads(Path(parsed.patch_file).read_text(encoding='utf-8'))['slot_data'])
        mode = {1: 'per_world', 2: 'anywhere'}.get(slot['options']['music_randomization'])
        if mode is None:
            parser.error('music_randomization is off in this seed')
        patch_music(*parsed.patch_music, slot['seed_name'], mode)
        logging.info('Music CPK and manifest created. Install into a separate disc copy; audible playback unverified.')
        return
    asyncio.run(main(parsed))


if __name__ == '__main__':
    launch_client(*sys.argv[1:])
