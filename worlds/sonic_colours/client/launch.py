import asyncio
import logging
import sys
from CommonClient import get_base_parser, handle_url_arg


def select_player_patch(parsed):
    if (parsed.patch_file or parsed.url or parsed.connect
            or getattr(parsed,'nogui',False) or parsed.no_start_dolphin):
        return True
    from Utils import open_filename
    selected=open_filename('Select your Sonic Colours player patch',
        [('Sonic Colours player patch', ['.apsoniccolours','.apsonic'])])
    if not selected:return False
    parsed.patch_file=selected
    return True


def patch_server_address(patch,explicit=None,gui=True):
    """Never silently fall back to another room when a download lacks a port."""
    address=explicit or patch.server
    if not address and gui:
        import tkinter as tk
        from tkinter.simpledialog import askstring
        root=tk.Tk();root.withdraw()
        try:
            address=askstring('Archipelago room address',
                'This patch has no room address. Start the room on the website, then enter its address and port (host:port).',
                parent=root)
        finally:root.destroy()
    if not address:
        raise ValueError('Player patch has no server address. Supply --connect HOST:PORT or download it again after the room has started.')
    from urllib.parse import urlsplit
    address=address.strip()
    endpoint=urlsplit(address if '://' in address else 'ws://'+address)
    if (endpoint.scheme not in ('ws','wss') or not endpoint.hostname or endpoint.port is None or endpoint.port<1
            or endpoint.username or endpoint.password or endpoint.path not in ('','/') or endpoint.query or endpoint.fragment):
        raise ValueError('Use an Archipelago host and explicit port, for example archipelago.gg:38281.')
    return address


def launch_client(*args):
    from .client import main
    parser = get_base_parser(description='Sonic Colours PAL Archipelago Client')
    parser.add_argument('--name', help='Archipelago slot name')
    parser.add_argument('--original-iso',help='Original PAL SNCP8P Rev0 ISO (saved path/file selection otherwise)')
    parser.add_argument('--output-iso',help='Separate output ISO; existing mismatching files are never overwritten')
    parser.add_argument('--wit',help='Wiimms ISO Tools executable; Windows download is verified automatically')
    parser.add_argument('--patch-only',action='store_true',help='Build/verify the ISO, then exit')
    parser.add_argument('--dolphin',help='Dolphin executable for optional automatic start')
    parser.add_argument('--start-dolphin',action='store_true',help='Start the generated ISO in Dolphin')
    parser.add_argument('--no-start-dolphin',action='store_true',help='Open the AP client without starting Dolphin')
    parser.add_argument('--migrate-seed-patch',nargs=2,metavar=('OLD_APSONIC','NEW_APSONICCOLOURS'))
    parser.add_argument('--player-slot',type=int,help='Explicit AP slot number for legacy patch migration')
    parser.add_argument('--experimental-direct-hooks', action='store_true',
                        help='DANGEROUS: no Gecko allowed; inject PAL PPC hooks plus optional movement gate; may crash, JIT unverified')
    parser.add_argument('--migrate-yaml', nargs=2, metavar=('OLD_YAML','NEW_YAML'),
                        help='Migrate older player YAMLs; verify schema 7 options before playing; seed files and journals are not migrated')
    parser.add_argument('--patch-music', nargs=2, metavar=('ORIGINAL_CPK', 'OUTPUT_CPK'),
                        help='Build a separate seed music CPK from the .apsonic file, then exit')
    parser.add_argument('--patch-all-music', nargs=2, metavar=('ORIGINAL_CPK', 'OUTPUT_CPK'),
                        help='Redirect compatible stage, boss, map, title, menu and Game Land BGM in a separate PAL CPK, then exit')
    parser.add_argument('--music-resource-manifest', metavar='PATCHED_CPK_JSON',
                        help='Select the seed BGM resource manifest and suppress duplicate runtime shuffling; loaded Dolphin playback remains unverified')
    parser.add_argument('url', nargs='?', help='archipelago:// URI or .apsonic file')
    parsed = parser.parse_args(args)
    parsed.patch_file = None
    if parsed.url and parsed.url.lower().endswith(('.apsonic','.apsoniccolours')):
        parsed.patch_file, parsed.url = parsed.url, None
    else:
        parsed = handle_url_arg(parsed, parser=parser)
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')
    try:
        from .file_association import register_windows_patch
        register_windows_patch()
    except OSError as error:logging.info('Windows file association unavailable; Open Patch still works: %s',error)
    if parsed.migrate_seed_patch:
        from ..patch import migrate_legacy
        migrate_legacy(*parsed.migrate_seed_patch,parsed.player_slot)
        logging.info('Legacy metadata migrated without modifying its source.');return
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
    if parsed.patch_music and parsed.patch_all_music:
        parser.error('choose --patch-music or --patch-all-music')
    if parsed.patch_music or parsed.patch_all_music:
        if not parsed.patch_file:
            parser.error('--patch-music requires a generated .apsonic file')
        import json
        from pathlib import Path
        from .runtime import validate_slot
        from .asset_patch import patch_music
        from ..patch import load_patch
        slot = load_patch(parsed.patch_file).slot_data
        mode = 'anywhere' if slot['options']['music_randomization'] else None
        if mode is None:
            parser.error('music_randomization is off in this seed')
        if parsed.patch_all_music:
            from .music_bank import patch
            patch(*parsed.patch_all_music, slot['seed_name'], mode,slot.get('music_mapping_version',1),music_seed=slot.get('music_seed'))
        else:
            patch_music(*parsed.patch_music, slot['seed_name'], mode,slot.get('music_mapping_version',1),music_seed=slot.get('music_seed'))
        logging.info('Separate seed music CPK and manifest verified. Install into a separate disc copy and restart emulation; file creation does not verify Dolphin playback.')
        return
    # The Launcher component and Open Patch enter the same installation flow.
    # Explicit URL/headless/client-only invocations retain their CLI behavior.
    if not select_player_patch(parsed):return
    parsed.generated_iso=None
    parsed.dolphin_launch_status=None
    if parsed.patch_file:
        from ..patch import load_patch
        from .iso_patch import install,install_with_progress,settings_group
        patch=load_patch(parsed.patch_file)
        if not parsed.patch_only:
            try:
                parsed.connect=patch_server_address(patch,parsed.connect,not getattr(parsed,'nogui',False))
                if not patch.server:
                    # Preserve the download. A separate official player patch
                    # remembers the supplied endpoint for subsequent launches.
                    from pathlib import Path
                    original=Path(parsed.patch_file)
                    target=original.with_name(original.stem+'_connected.apsoniccolours')
                    suffix=1
                    while target.exists():
                        target=original.with_name(original.stem+f'_connected_{suffix}.apsoniccolours');suffix+=1
                    patch.server=parsed.connect
                    with target.open('xb') as stream:patch.write(stream)
                    logging.info('Player patch with server address saved to %s',target)
                    parsed.patch_file=str(target)
            except (OSError,ValueError) as error:
                logging.error('Room address: %s',error)
                if not getattr(parsed,'nogui',False):
                    import Utils
                    Utils.messagebox('Archipelago room address',str(error),error=True)
                return
        group=settings_group()
        automatic=(not parsed.no_start_dolphin and (parsed.start_dolphin or
                   not parsed.patch_only and (bool(group.auto_start) or
                   not vars(group).get('dolphin_path'))))
        executable=None
        if automatic:
            from .dolphin_launch import select_executable
            try:executable=select_executable(group,parsed.dolphin,not getattr(parsed,'nogui',False))
            except (OSError,ValueError) as error:
                logging.error('Dolphin selection failed: %s',error)
                if not getattr(parsed,'nogui',False):
                    import Utils
                    Utils.messagebox('Dolphin selection',str(error),error=True)
                return
        installer=install if getattr(parsed,'nogui',False) else install_with_progress
        try:
            parsed.generated_iso=str(installer(patch,source=parsed.original_iso,target=parsed.output_iso,wit=parsed.wit))
        except Exception as error:
            logging.error('ISO installation failed: %s',error)
            if not getattr(parsed,'nogui',False):
                import Utils
                Utils.messagebox('Sonic Colours ISO patch failed',str(error),error=True)
            return
        if not parsed.connect and patch.server:parsed.connect=patch.server
        if automatic and executable:
            from .dolphin_launch import start_or_reuse
            try:
                parsed.dolphin_launch_status=start_or_reuse(executable,parsed.generated_iso)
            except (OSError,ValueError) as error:
                logging.error('Dolphin startup: %s',error)
                if not getattr(parsed,'nogui',False):
                    import Utils
                    Utils.messagebox('Dolphin startup',str(error),error=True)
        if parsed.patch_only:return
    elif parsed.patch_only:parser.error('--patch-only requires a player patch')
    asyncio.run(main(parsed))


if __name__ == '__main__':
    launch_client(*sys.argv[1:])
