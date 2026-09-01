from worlds.LauncherComponents import (
    Component,
    SuffixIdentifier,
    Type,
    components,
    icon_paths,
    launch,
)

from .world_constants import GAME_NAME


CREATE_ICON = "create"
icon_paths[CREATE_ICON] = "ap:worlds.create/assets/Create AP Logo.png"


def run_client(*args: str) -> None:
    from .client.launch import launch_create_client

    launch(launch_create_client, name="CreateClient", args=args)


components.append(
    Component(
        "Create Client",
        func=run_client,
        game_name=GAME_NAME,
        component_type=Type.CLIENT,
        icon=CREATE_ICON,
        file_identifier=SuffixIdentifier(".apcreate"),
        supports_uri=True,
    )
)
