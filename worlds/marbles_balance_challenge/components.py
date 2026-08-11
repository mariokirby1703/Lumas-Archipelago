from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, launch

from .world_constants import GAME_NAME


def run_client(*args: str) -> None:
    from .client.launch import launch_marble_balance_client

    launch(launch_marble_balance_client, name="MarbleBalanceClient", args=args)


components.append(
    Component(
        "Marbles! Balance Challenge Client",
        func=run_client,
        game_name=GAME_NAME,
        component_type=Type.CLIENT,
        file_identifier=SuffixIdentifier(".apmbc"),
        supports_uri=True,
    )
)
