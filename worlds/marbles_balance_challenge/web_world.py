from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld

from .Options import option_groups, option_presets
from .world_constants import GAME_NAME


class MarbleBalanceWebWorld(WebWorld):
    game = GAME_NAME
    theme = "ocean"
    option_groups = option_groups
    options_presets = option_presets

    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up Marbles! Balance Challenge for MultiWorld.",
            "English",
            "setup_en.md",
            "setup/en",
            ["TomGo", "Codex"],
        )
    ]

