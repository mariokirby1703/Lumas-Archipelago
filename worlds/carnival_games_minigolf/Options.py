from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, PerGameCommonOptions, Range, Toggle


class StartingWorld(Choice):
    """World initially unlocked. Use YAML value `random` for randomization."""
    display_name = "Starting World"
    option_rahs_revenge = 0
    option_spook_o_rama = 1
    option_amazeon = 2
    option_kings_court = 3
    option_wild_west = 4
    option_prehistoria = 5
    option_barn_yard = 6
    option_pirates_delight = 7
    option_fairytella = 8
    default = "random"


class GoalWorld(StartingWorld):
    """Final world for Barker Goal World Requirement. Must differ from the starting world."""
    display_name = "Goal World"
    default = "random"


class Goal(Choice):
    """All Holes: finish every normal hole, without a Par requirement.
    Goal World: receive access, then finish its three holes on Par or better.
    Barker Coin Hunt: receive the configured number of AP Barker Coins.
    """
    display_name = "Goal"
    option_all_holes = 0
    option_goal_world = 1
    option_barker_coin_hunt = 2
    default = 0


class MinigameChecks(Choice):
    """Win Checks creates one Win location per minigame. Perfect Checks creates one Perfect location.
    Win + Perfect Checks creates TWO separate locations per minigame; a Perfect run completes both.
    """
    display_name = "Minigame Checks"
    option_off = 0
    option_win_checks = 1
    option_perfect_checks = 2
    option_win_and_perfect_checks = 3
    default = 1


class HoleInOneChecks(Toggle):
    """Add one Hole-in-One check for each normal hole."""
    display_name = "Hole-in-One Checks"


class BarkerCoinChecks(DefaultOnToggle):
    """Add the 27 collectible Barker Coin checks."""
    display_name = "Barker Coin Checks"


class WorldSecrets(DefaultOnToggle):
    """Add the nine world-map secret checks."""
    display_name = "World Secrets"


class ShopChecks(DefaultOnToggle):
    """Add 63 normal purchases and nine Par Club rewards.
    Logic assumes repeatable normal coin earnings; bundles are optional assistance.
    """
    display_name = "Shop Checks"


class BarkerShopChecks(DefaultOnToggle):
    """Add seven Barker purchases. Automatically disabled for Barker counter goals."""
    display_name = "Barker Shop Checks"


class GoalWorldAccess(Choice):
    """How Goal World Access enters the multiworld when Goal is Goal World.
    World Unlock Item places it normally. Barker Coins locks it on the Barker threshold location.
    """
    display_name = "Goal World Access"
    option_world_unlock_item = 0
    option_barker_coins = 1


class BarkerCoinsRequired(Range):
    """Received AP Barker Coins needed for Barker Coin Hunt or Barker Coins Goal World Access."""
    display_name = "Barker Coins Required"
    range_start = 1
    range_end = 50
    default = 27


class TrapWeight(Range):
    """Percentage of filler items that become Coin Traps."""
    display_name = "Trap Weight"
    range_start = 0
    range_end = 100
    default = 10


@dataclass
class MiniGolfOptions(PerGameCommonOptions):
    starting_world: StartingWorld
    goal_world: GoalWorld
    goal: Goal
    minigame_checks: MinigameChecks
    hole_in_one_checks: HoleInOneChecks
    barker_coin_checks: BarkerCoinChecks
    world_secrets: WorldSecrets
    shop_checks: ShopChecks
    barker_shop_checks: BarkerShopChecks
    goal_world_access: GoalWorldAccess
    barker_coins_required: BarkerCoinsRequired
    trap_weight: TrapWeight
