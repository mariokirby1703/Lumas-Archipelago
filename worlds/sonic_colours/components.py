from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, launch
from .world_constants import GAME


def run_client(*args):
    from .client.launch import launch_client
    launch(launch_client, name='SonicColoursClient', args=args)


components.append(Component('Sonic Colours Client', func=run_client, game_name=GAME,
                            component_type=Type.CLIENT, file_identifier=SuffixIdentifier('.apsonic'),
                            supports_uri=True))
