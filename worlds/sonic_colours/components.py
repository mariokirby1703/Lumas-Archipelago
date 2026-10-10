from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, icon_paths, launch
from .world_constants import GAME

ICON = 'sonic_colours'
icon_paths[ICON] = f'ap:{__package__}/assets/Colours Logo.png'


def run_client(*args):
    from .client.launch import launch_client
    launch(launch_client, name='SonicColoursClient', args=args)


components.append(Component('Sonic Colours (Wii) Client', func=run_client, game_name=GAME,
                            component_type=Type.CLIENT, file_identifier=SuffixIdentifier('.apsonic'),
                            supports_uri=True, icon=ICON))
