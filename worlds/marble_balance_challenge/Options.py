from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionGroup, PerGameCommonOptions, Range, Toggle


class Goal(Choice):
    """Which stage completion should be required to finish the slot."""

    display_name = "Goal"
    option_normal_w7_l10 = 0
    option_hard_w7_l10 = 1
    default = option_normal_w7_l10


class IncludedDifficulties(Choice):
    """Which campaign difficulties are represented as Archipelago locations."""

    display_name = "Included Difficulties"
    option_normal = 0
    option_easy_and_normal = 1
    option_normal_and_hard = 2
    option_all = 3
    default = option_normal


class GreenGemSanity(Toggle):
    """Add one Green Gem location to normal difficulty campaign levels that have a Green Gem."""

    display_name = "Green Gem Sanity"


class StumpPieceSanity(Toggle):
    """Add Stump Temple Piece locations to all stages that have a Stump Temple Piece."""

    display_name = "Stump Temple Piece Sanity"


class AnthonySanity(Toggle):
    """Add Anthony locations from Hard difficulty stages 01 through 10."""

    display_name = "Anthony Sanity"


class TrophySanity(Choice):
    """Add trophy locations for the selected trophy tier."""

    display_name = "Trophy Sanity"
    option_off = 0
    option_bronze = 1
    option_silver = 2
    option_gold = 3
    option_platinum = 4
    option_all = 5
    default = option_off


class RequiredStumpPiecesForW7(Range):
    """Number of AP-side Stump Temple Pieces required to reach Stump Temple."""

    display_name = "Required Stump Temple Pieces for W7"
    range_start = 30
    range_end = 90
    default = 60


class HardModeUnlock(Choice):
    """How Hard Mode is unlocked when Hard locations or the Hard goal are enabled."""

    display_name = "Hard Mode Unlock"
    option_start = 0
    option_item = 1
    option_green_gems = 2
    option_vanilla = 3
    default = option_item


class RequiredGreenGemsForHard(Range):
    """Number of AP-side Green Gems required when Hard Mode Unlock is set to Green Gems."""

    display_name = "Required Green Gems for Hard Mode"
    range_start = 0
    range_end = 60
    default = 30


class TutorialChecks(Toggle):
    """Include Tutorial 01 through Tutorial 10 as early checks."""

    display_name = "Tutorial Checks"


class WiiBalanceBoardLevels(Toggle):
    """Include Wii Balance Board Level 01 through Level 100 checks."""

    display_name = "Wii Balance Board Levels"


class RecipeAndJunkFactory(Toggle):
    """Shuffle confirmed recipe unlocks and Junk Factory access."""

    display_name = "Recipes and Junk Factory"


class TrapChance(Range):
    """Percentage chance for filler to become one of the experimental traps."""

    display_name = "Trap Chance"
    range_start = 0
    range_end = 50
    default = 10


class SplitVehicleWorldAccess(DefaultOnToggle):
    """Require both the vehicle item and matching world access item for W5/W6 logic."""

    display_name = "Split Vehicle World Access"


@dataclass
class MarbleBalanceOptions(PerGameCommonOptions):
    goal: Goal
    included_difficulties: IncludedDifficulties
    green_gem_sanity: GreenGemSanity
    stump_piece_sanity: StumpPieceSanity
    required_stump_pieces_for_w7: RequiredStumpPiecesForW7
    hard_mode_unlock: HardModeUnlock
    required_green_gems_for_hard: RequiredGreenGemsForHard
    tutorial_checks: TutorialChecks
    wii_balance_board_levels: WiiBalanceBoardLevels
    recipe_and_junk_factory: RecipeAndJunkFactory
    trap_chance: TrapChance
    split_vehicle_world_access: SplitVehicleWorldAccess
    anthony_sanity: AnthonySanity
    trophy_sanity: TrophySanity


option_groups = [
    OptionGroup(
        "Campaign",
        [
            Goal,
            IncludedDifficulties,
            TutorialChecks,
            WiiBalanceBoardLevels,
        ],
    ),
    OptionGroup(
        "Logic",
        [
            GreenGemSanity,
            StumpPieceSanity,
            RequiredStumpPiecesForW7,
            HardModeUnlock,
            RequiredGreenGemsForHard,
            SplitVehicleWorldAccess,
            AnthonySanity,
            TrophySanity,
        ],
    ),
    OptionGroup(
        "Item Pool",
        [
            RecipeAndJunkFactory,
            TrapChance,
        ],
    ),
]

option_presets = {
    "Test Profile": {
        "goal": "normal_w7_l10",
        "included_difficulties": "normal",
        "green_gem_sanity": False,
        "stump_piece_sanity": False,
        "tutorial_checks": False,
        "wii_balance_board_levels": False,
        "recipe_and_junk_factory": False,
        "anthony_sanity": False,
        "trophy_sanity": "off",
        "trap_chance": 10,
    },
    "Counter Logic": {
        "goal": "normal_w7_l10",
        "included_difficulties": "normal",
        "green_gem_sanity": True,
        "stump_piece_sanity": True,
        "required_stump_pieces_for_w7": 60,
    },
    "Hard Goal": {
        "goal": "hard_w7_l10",
        "included_difficulties": "normal_and_hard",
        "green_gem_sanity": True,
        "stump_piece_sanity": True,
        "hard_mode_unlock": "item",
        "required_stump_pieces_for_w7": 60,
        "anthony_sanity": True,
    },
}
