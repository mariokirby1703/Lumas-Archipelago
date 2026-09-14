from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, launch

from .data import GAME


def run_client(*args):
    from .client.launch import launch_client
    launch(launch_client, name="CarnivalGamesMiniGolfClient", args=args)


components.append(Component("Carnival Games MiniGolf Client", func=run_client, game_name=GAME,
                            component_type=Type.CLIENT, file_identifier=SuffixIdentifier(".apcgm"),
                            supports_uri=True))
