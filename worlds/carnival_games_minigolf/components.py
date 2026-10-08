from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, icon_paths, launch

from .data import GAME

ICON = "carnival_games_minigolf"
icon_paths[ICON] = f"ap:{__package__}/assets/MiniGolf Logo.png"


def run_client(*args):
    from .client.launch import launch_client
    launch(launch_client, name="CarnivalGamesMiniGolfClient", args=args)


components.append(Component("Carnival Games MiniGolf Client", func=run_client, game_name=GAME,
                            component_type=Type.CLIENT, file_identifier=SuffixIdentifier(".apcgm"),
                            supports_uri=True, icon=ICON))
