from worlds.LauncherComponents import (
    Component,
    SuffixIdentifier,
    Type,
    components,
    icon_paths,
    launch,
)

from .world_constants import GAME_NAME


MARBLES_ICON = "marbles_balance_challenge"
icon_paths[MARBLES_ICON] = (
    "ap:worlds.marbles_balance_challenge/assets/Marble Logo.png"
)


def run_client(*args: str) -> None:
    from .client.launch import launch_marble_balance_client

    launch(launch_marble_balance_client, name="MarbleBalanceClient", args=args)


components.append(
    Component(
        "Marbles! Balance Challenge Client",
        func=run_client,
        game_name=GAME_NAME,
        component_type=Type.CLIENT,
        icon=MARBLES_ICON,
        file_identifier=SuffixIdentifier(".apmbc"),
        supports_uri=True,
    )
)
