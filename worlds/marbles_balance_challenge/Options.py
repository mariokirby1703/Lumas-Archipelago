from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionGroup, PerGameCommonOptions, Range, Toggle


class Goal(Choice):
    """Which stage completion should be required to finish the slot."""

    display_name = "Goal"
    option_stump_temple_level_10_normal = 0
    option_stump_temple_level_10_hard = 1
    alias_normal_w7_l10 = 0
    alias_hard_w7_l10 = 1
    default = option_stump_temple_level_10_normal


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


class StumpPieceSanity(DefaultOnToggle):
    """Add Kororin Capsule locations to all stages that have a Kororin Capsule."""

    display_name = "Kororin Capsule Sanity"


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
    """Number of AP-side Stump Temple Pieces required to reach Stump Temple in your selected Goal Difficulty."""

    display_name = "Required Stump Temple Pieces for Stump Temple Goal World Unlock"
    range_start = 20
    range_end = 60
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
    range_start = 10
    range_end = 70
    default = 30


class ExtraCounterItemPercentage(Range):
    """Percent of extra AP-side Green Gem and Stump Temple Piece counter items added above the requirement."""

    display_name = "Extra Counter Item Percentage"
    range_start = 0
    range_end = 100
    default = 25


class TutorialChecks(Toggle):
    """Include Tutorial 01 through Tutorial 10 as early checks."""

    display_name = "Tutorial Checks"


class WiiBalanceBoardLevels(Toggle):
    """Include Wii Balance Board Level 01 through Level 100 checks."""

    display_name = "Wii Balance Board Levels"


class TrapChance(Range):
    """Percentage chance for filler to become one of the experimental traps."""

    display_name = "Trap Chance"
    range_start = 0
    range_end = 50
    default = 10


class TrapWeight(Choice):
    """Relative weight for this trap when a filler item becomes a trap."""

    option_low = 0
    option_medium = 1
    option_high = 2
    default = option_medium


class BlackoutTrapWeight(TrapWeight):
    """Relative chance for Blackout Trap when a filler item becomes a trap."""

    display_name = "Blackout Trap Weight"


class MirrorTrapWeight(TrapWeight):
    """Relative chance for Mirror Trap when a filler item becomes a trap."""

    display_name = "Mirror Trap Weight"


class InverseTrapWeight(TrapWeight):
    """Relative chance for Inverse Trap when a filler item becomes a trap."""

    display_name = "Inverse Trap Weight"
    default = TrapWeight.option_low


class NoclipTrapWeight(TrapWeight):
    """Relative chance for Noclip Trap when a filler item becomes a trap."""

    display_name = "Noclip Trap Weight"


class SplitVehicleWorldAccess(DefaultOnToggle):
    """Require both the vehicle item and matching world access item for W5/W6 logic."""

    display_name = "Split Vehicle World Access"


class RandomStartingWorld(DefaultOnToggle):
    """Start with one random accessible world per enabled difficulty."""

    display_name = "Random Starting World"


@dataclass
class MarbleBalanceOptions(PerGameCommonOptions):
    goal: Goal
    included_difficulties: IncludedDifficulties
    green_gem_sanity: GreenGemSanity
    stump_piece_sanity: StumpPieceSanity
    required_stump_pieces_for_w7: RequiredStumpPiecesForW7
    hard_mode_unlock: HardModeUnlock
    required_green_gems_for_hard: RequiredGreenGemsForHard
    extra_counter_item_percentage: ExtraCounterItemPercentage
    tutorial_checks: TutorialChecks
    wii_balance_board_levels: WiiBalanceBoardLevels
    trap_chance: TrapChance
    blackout_trap_weight: BlackoutTrapWeight
    mirror_trap_weight: MirrorTrapWeight
    inverse_trap_weight: InverseTrapWeight
    noclip_trap_weight: NoclipTrapWeight
    split_vehicle_world_access: SplitVehicleWorldAccess
    random_starting_world: RandomStartingWorld
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
            RandomStartingWorld,
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
            ExtraCounterItemPercentage,
            SplitVehicleWorldAccess,
            AnthonySanity,
            TrophySanity,
        ],
    ),
    OptionGroup(
        "Item Pool",
        [
            TrapChance,
            BlackoutTrapWeight,
            MirrorTrapWeight,
            InverseTrapWeight,
            NoclipTrapWeight,
        ],
    ),
]

option_presets = {
    "Test Profile": {
        "goal": "stump_temple_level_10_normal",
        "included_difficulties": "normal",
        "green_gem_sanity": False,
        "stump_piece_sanity": True,
        "tutorial_checks": False,
        "wii_balance_board_levels": False,
        "random_starting_world": True,
        "extra_counter_item_percentage": 25,
        "anthony_sanity": False,
        "trophy_sanity": "off",
        "trap_chance": 10,
        "blackout_trap_weight": "medium",
        "mirror_trap_weight": "medium",
        "inverse_trap_weight": "low",
        "noclip_trap_weight": "medium",
    },
    "Counter Logic": {
        "goal": "stump_temple_level_10_normal",
        "included_difficulties": "normal",
        "green_gem_sanity": True,
        "stump_piece_sanity": True,
        "required_stump_pieces_for_w7": 60,
        "extra_counter_item_percentage": 25,
        "random_starting_world": True,
    },
    "Hard Goal": {
        "goal": "stump_temple_level_10_hard",
        "included_difficulties": "normal_and_hard",
        "green_gem_sanity": True,
        "stump_piece_sanity": True,
        "hard_mode_unlock": "item",
        "required_stump_pieces_for_w7": 60,
        "extra_counter_item_percentage": 25,
        "random_starting_world": True,
        "anthony_sanity": True,
    },
}
