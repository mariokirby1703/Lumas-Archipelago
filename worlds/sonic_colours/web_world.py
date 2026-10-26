from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld
from .Options import OPTION_GROUPS


class SonicColoursWeb(WebWorld):
    theme = 'ocean'
    game_info_files = {'en':'sonic_colours.md'}
    option_groups = OPTION_GROUPS
    tutorials = [Tutorial('Multiworld Setup', 'PAL Dolphin client setup and validation limitations.',
                          'English', 'setup.md', 'setup', ['Luma'])]
