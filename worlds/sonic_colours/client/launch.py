import asyncio
import logging
import sys
from CommonClient import get_base_parser, handle_url_arg


def launch_client(*args):
    from .client import main
    parser = get_base_parser(description='Sonic Colours PAL Archipelago Client')
    parser.add_argument('--name', help='Archipelago slot name')
    parser.add_argument('--export-capsule-gecko', metavar='OUTPUT_INI',
                        help='Export all four PAL native Gecko code groups and exit')
    parser.add_argument('--migrate-yaml', nargs=2, metavar=('OLD_YAML','NEW_YAML'),
                        help='Migrate a player YAML to schema 5 and exit; seed files and journals are not migrated')
    parser.add_argument('--patch-music', nargs=2, metavar=('ORIGINAL_CPK', 'OUTPUT_CPK'),
                        help='Build a separate seed music CPK from the .apsonic file, then exit')
    parser.add_argument('--patch-all-music', nargs=2, metavar=('ORIGINAL_CPK', 'OUTPUT_CPK'),
                        help='Redirect compatible stage, boss, map, title, menu and Game Land BGM in a separate PAL CPK, then exit')
    parser.add_argument('--music-resource-manifest', metavar='PATCHED_CPK_JSON',
                        help='Select the seed BGM resource manifest and suppress duplicate runtime shuffling; loaded Dolphin playback remains unverified')
    parser.add_argument('url', nargs='?', help='archipelago:// URI or .apsonic file')
    parsed = parser.parse_args(args)
    parsed.patch_file = None
    if parsed.url and parsed.url.lower().endswith('.apsonic'):
        parsed.patch_file, parsed.url = parsed.url, None
    else:
        parsed = handle_url_arg(parsed, parser=parser)
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
    if parsed.migrate_yaml:
        import yaml
        from pathlib import Path
        from ..migration import migrate_yaml
        original,output=map(Path,parsed.migrate_yaml)
        if output.exists():parser.error('migration output already exists; choose a new output path')
        migrated,changes=migrate_yaml(yaml.safe_load(original.read_text(encoding='utf-8')))
        output.write_text(yaml.safe_dump(migrated,sort_keys=False),encoding='utf-8')
        for change in changes:logging.info(change)
        return
    if parsed.export_capsule_gecko:
        from pathlib import Path
        from .capsule_refresh import gecko_ini
        Path(parsed.export_capsule_gecko).write_text(gecko_ini(), encoding='utf-8')
        logging.info('Four PAL native code groups exported. Enable all four in Dolphin before starting emulation; runtime verification is still required.')
        return
    if parsed.patch_music and parsed.patch_all_music:
        parser.error('choose --patch-music or --patch-all-music')
    if parsed.patch_music or parsed.patch_all_music:
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
        if parsed.patch_all_music:
            from .music_bank import patch
            patch(*parsed.patch_all_music, slot['seed_name'], mode)
        else:
            patch_music(*parsed.patch_music, slot['seed_name'], mode)
        logging.info('Separate seed music CPK and manifest verified. Install into a separate disc copy and restart emulation; file creation does not verify Dolphin playback.')
        return
    asyncio.run(main(parsed))


if __name__ == '__main__':
    launch_client(*sys.argv[1:])
