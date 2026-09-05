from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionGroup, PerGameCommonOptions, Range, Toggle

from .world_constants import WORLD_NAMES


class StartingWorld(Choice):
    """World that starts unlocked. Random chooses from the enabled worlds.
    Selecting a II world includes it even when Include II Worlds is disabled.
    """

    display_name = "Starting World"
    option_random_world = 0
    option_theme_park = 1
    option_transportopia = 2
    option_family_home = 3
    option_outer_space = 4
    option_the_great_outdoors = 5
    option_ancient_history = 6
    option_future_world = 7
    option_urban_sports = 8
    option_pirate = 9
    option_darkworld = 10
    option_theme_park_ii = 11
    option_family_home_ii = 12
    option_outer_space_ii = 13
    option_future_world_ii = 14
    default = "random"

    @classmethod
    def from_text(cls, text: str):
        if text.lower() == "random":
            return cls(cls.option_random_world)
        return super().from_text(text)

    @classmethod
    def get_option_name(cls, value: int) -> str:
        if value == cls.option_random_world:
            return "Random"
        return WORLD_NAMES[value_to_world_key(value)]


class GoalWorld(Choice):
    """Earn the first Spark in Challenge 10 of this world to finish Goal World Unlock.
    Required Sparks gates access to this world. Ignored in Spark Hunt with a positive requirement.
    """

    display_name = "Goal World"
    option_random_world = 0
    option_theme_park = 1
    option_transportopia = 2
    option_family_home = 3
    option_outer_space = 4
    option_the_great_outdoors = 5
    option_ancient_history = 6
    option_future_world = 7
    option_urban_sports = 8
    option_pirate = 9
    option_darkworld = 10
    option_theme_park_ii = 11
    option_family_home_ii = 12
    option_outer_space_ii = 13
    option_future_world_ii = 14
    default = "random"

    @classmethod
    def from_text(cls, text: str):
        if text.lower() == "random":
            return cls(cls.option_random_world)
        return super().from_text(text)

    @classmethod
    def get_option_name(cls, value: int) -> str:
        if value == cls.option_random_world:
            return "Random"
        return WORLD_NAMES[value_to_world_key(value)]


def value_to_world_key(value: int) -> str:
    return f"W{value:02d}"


class CreateChainChecks(DefaultOnToggle):
    """Add 5 Create Chain checks per world."""

    display_name = "Create Chain Checks"


class IncludeIIWorlds(Toggle):
    """Include Theme Park II, Family Home II, Outer Space II, and Future World II."""

    display_name = "Include II Worlds"


class RequiredSparks(Range):
    """Archipelago Sparks needed to unlock the goal world or finish Spark Hunt.
    With 0, Spark Goal Mode is ignored: goal world access is a normal Archipelago item,
    and completing the goal world's final challenge finishes the game.
    """

    display_name = "Required Sparks"
    range_start = 0
    range_end = 610
    default = 100


class SparkGoalMode(Choice):
    """Goal World Unlock requires the goal world's final challenge and the required Sparks.
    Spark Hunt finishes on collecting the required Sparks, without a final challenge.
    Ignored when Required Sparks is 0.
    """

    display_name = "Spark Goal Mode"
    option_goal_world_unlock = 0
    option_spark_hunt = 1
    default = 0


@dataclass
class CreateOptions(PerGameCommonOptions):
    starting_world: StartingWorld
    goal_world: GoalWorld
    create_chain_checks: CreateChainChecks
    include_ii_worlds: IncludeIIWorlds
    required_sparks: RequiredSparks
    spark_goal_mode: SparkGoalMode


option_groups = [
    OptionGroup(
        "Worlds",
        [
            StartingWorld,
            GoalWorld,
            CreateChainChecks,
            IncludeIIWorlds,
            RequiredSparks,
            SparkGoalMode,
        ],
    ),
]


option_presets = {
    "Standard": {
        "starting_world": "random",
        "goal_world": "random",
        "create_chain_checks": True,
        "include_ii_worlds": False,
        "required_sparks": 100,
        "spark_goal_mode": "goal_world_unlock",
    },
    "Compact": {
        "starting_world": "random",
        "goal_world": "random",
        "create_chain_checks": True,
        "include_ii_worlds": False,
        "required_sparks": 100,
        "spark_goal_mode": "goal_world_unlock",
    },
}
