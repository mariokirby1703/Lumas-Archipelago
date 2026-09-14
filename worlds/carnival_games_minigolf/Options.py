from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, PerGameCommonOptions, Range, Toggle


class StartingWorld(Choice):
    """World initially unlocked. Random is resolved once by the generator."""
    display_name = "Starting World"
    option_random_world = 0
    option_rahs_revenge = 1
    option_spook_o_rama = 2
    option_amazeon = 3
    option_kings_court = 4
    option_wild_west = 5
    option_prehistoria = 6
    option_barn_yard = 7
    option_pirates_delight = 8
    option_fairytella = 9
    default = 0

    @classmethod
    def from_text(cls, text):
        if text.lower() == "random":
            return cls(0)
        return super().from_text(text)


class GoalWorld(StartingWorld):
    """Final world for Barker Goal World Requirement. Must differ from the starting world."""
    display_name = "Goal World"


class Goal(Choice):
    """Complete all 27 holes on par, or receive the required AP Barker Coins.
    Barker Goal World Requirement overrides the finish with three final-world par clears.
    """
    display_name = "Goal"
    option_all_27_holes_on_par = 0
    option_barker_coin_hunt = 1
    default = 0


class MinigameChecks(Choice):
    """Check minigame wins, perfect results, both, or neither."""
    display_name = "Minigame Checks"
    option_off = 0
    option_win = 1
    option_perfect = 2
    option_win_and_perfect = 3
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


class BarkerGoalWorldRequirement(Toggle):
    """Receive the required Barker Coins to open the final world, then par all three holes there."""
    display_name = "Barker Goal World Requirement"


class BarkerCoinsRequired(Range):
    """Number of received AP Barker Coins needed for the hunt or final-world gate."""
    display_name = "Barker Coins Required"
    range_start = 1
    range_end = 27
    default = 27


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
    barker_goal_world_requirement: BarkerGoalWorldRequirement
    barker_coins_required: BarkerCoinsRequired
