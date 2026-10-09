from dataclasses import dataclass
from Options import Choice, DefaultOnToggle, Toggle, Range, DeathLink, PerGameCommonOptions, OptionGroup

class Goal(Choice):
    """Victory requires an observed native game event."""
    display_name = 'Goal'
    option_final_boss = 0
    option_all_story_clears = 1
    option_all_red_rings = 2
    option_all_game_land = 3
    option_super_sonic = 4
    default = 0


class RedRingChecks(Choice):
    """Physical Red Ring locations, independent from AP Red Ring inventory."""
    display_name = 'Red Ring Checks'
    option_off = 0
    option_singles = 1
    option_per_level = 2
    default = 1


class WispUnlocks(Choice):
    """AP permissions include White Boost; native hook requires validation."""
    display_name = 'Wisp Unlocks'
    option_vanilla = 0
    option_archipelago = 1
    default = 1


class WorldUnlocks(Choice):
    """World Access items control map access."""
    display_name = 'World Unlocks'
    option_vanilla = 0
    option_archipelago = 1
    default = 1


class StartingAct(Choice):
    """Initial menu slot, deriving its starting world."""
    display_name = 'Starting Act'
    option_tropical_resort_act_1 = 0
    option_tropical_resort_act_2 = 1
    option_tropical_resort_act_3 = 2
    option_tropical_resort_act_4 = 3
    option_tropical_resort_act_5 = 4
    option_tropical_resort_act_6 = 5
    option_sweet_mountain_act_1 = 6
    option_sweet_mountain_act_2 = 7
    option_sweet_mountain_act_3 = 8
    option_sweet_mountain_act_4 = 9
    option_sweet_mountain_act_5 = 10
    option_sweet_mountain_act_6 = 11
    option_starlight_carnival_act_1 = 12
    option_starlight_carnival_act_2 = 13
    option_starlight_carnival_act_3 = 14
    option_starlight_carnival_act_4 = 15
    option_starlight_carnival_act_5 = 16
    option_starlight_carnival_act_6 = 17
    option_planet_wisp_act_1 = 18
    option_planet_wisp_act_2 = 19
    option_planet_wisp_act_3 = 20
    option_planet_wisp_act_4 = 21
    option_planet_wisp_act_5 = 22
    option_planet_wisp_act_6 = 23
    option_aquarium_park_act_1 = 24
    option_aquarium_park_act_2 = 25
    option_aquarium_park_act_3 = 26
    option_aquarium_park_act_4 = 27
    option_aquarium_park_act_5 = 28
    option_aquarium_park_act_6 = 29
    option_asteroid_coaster_act_1 = 30
    option_asteroid_coaster_act_2 = 31
    option_asteroid_coaster_act_3 = 32
    option_asteroid_coaster_act_4 = 33
    option_asteroid_coaster_act_5 = 34
    option_asteroid_coaster_act_6 = 35
    default = 0


class LevelRandomization(Choice):
    """Experimental: rejected until native mission replacement is validated."""
    display_name = 'Level Randomization'
    option_off = 0
    option_per_world = 1
    option_anywhere = 2
    default = 0


class RankChecks(Choice):
    """Minimum awarded quality. All creates five locations. Requires live validation."""
    display_name = 'Rank Checks'
    option_off = 0
    option_s = 1
    option_a = 2
    option_b = 3
    option_c = 4
    option_d = 5
    option_all = 6
    default = 0


class RingLossTrapWeight(Choice):
    """Relative trap weights: 0, 1, 3, 6."""
    display_name = 'Ring Loss Trap Weight'
    option_off = 0
    option_low = 1
    option_medium = 2
    option_high = 3
    default = 2


class SwimTrapWeight(Choice):
    """Experimental swimming hook is disabled until reversible state is proven."""
    display_name = 'Swim Trap Weight'
    option_off = 0
    option_low = 1
    option_medium = 2
    option_high = 3
    default = 0


class MusicRandomization(Choice):
    """Experimental: rejected until assets and playback replacement are validated."""
    display_name = 'Music Randomization'
    option_off = 0
    option_per_world = 1
    option_anywhere = 2
    default = 0


class RedRingBundleStrategy(Choice):
    """Exact AP counter packing with denominations 1, 5 and 10."""
    display_name = 'Red Ring Bundle Strategy'
    option_auto = 0
    option_small = 1
    option_medium = 2
    option_large = 3
    default = 0


class GameLandChecks(DefaultOnToggle):
    """Enable game land checks."""
    display_name = 'Game Land Checks'


class ChaosEmeraldChecks(DefaultOnToggle):
    """Enable chaos emerald checks."""
    display_name = 'Chaos Emerald Checks'


class ChaosEmeraldItems(DefaultOnToggle):
    """Enable chaos emerald items."""
    display_name = 'Chaos Emerald Items'


class SuperSonicItem(Toggle):
    """Enable super sonic item."""
    display_name = 'Super Sonic Item'


class WispDiscoveryChecks(Toggle):
    """Enable wisp discovery checks."""
    display_name = 'Wisp Discovery Checks'


class GameLandRequirementReduction(Range):
    """Configure game land requirement reduction."""
    display_name = 'Game Land Requirement Reduction'
    range_start = 0
    range_end = 179
    default = 40


class TrapPercentage(Range):
    """Configure trap percentage."""
    display_name = 'Trap Percentage'
    range_start = 0
    range_end = 100
    default = 10


class SwimTrapDuration(Range):
    """Configure swim trap duration."""
    display_name = 'Swim Trap Duration'
    range_start = 5
    range_end = 60
    default = 15


@dataclass
class SonicColoursOptions(PerGameCommonOptions):
    goal: Goal
    red_ring_checks: RedRingChecks
    wisp_unlocks: WispUnlocks
    world_unlocks: WorldUnlocks
    starting_act: StartingAct
    level_randomization: LevelRandomization
    rank_checks: RankChecks
    ring_loss_trap_weight: RingLossTrapWeight
    swim_trap_weight: SwimTrapWeight
    music_randomization: MusicRandomization
    red_ring_bundle_strategy: RedRingBundleStrategy
    game_land_checks: GameLandChecks
    chaos_emerald_checks: ChaosEmeraldChecks
    chaos_emerald_items: ChaosEmeraldItems
    super_sonic_item: SuperSonicItem
    wisp_discovery_checks: WispDiscoveryChecks
    game_land_requirement_reduction: GameLandRequirementReduction
    trap_percentage: TrapPercentage
    swim_trap_duration: SwimTrapDuration
    death_link: DeathLink

OPTION_NAMES = ('goal', 'red_ring_checks', 'wisp_unlocks', 'world_unlocks', 'starting_act', 'level_randomization', 'rank_checks', 'ring_loss_trap_weight', 'swim_trap_weight', 'music_randomization', 'red_ring_bundle_strategy', 'game_land_checks', 'chaos_emerald_checks', 'chaos_emerald_items', 'super_sonic_item', 'wisp_discovery_checks', 'game_land_requirement_reduction', 'trap_percentage', 'swim_trap_duration', 'death_link')

OPTION_GROUPS = [
    OptionGroup("Progression", [Goal, StartingAct, WorldUnlocks, WispUnlocks, ChaosEmeraldItems, SuperSonicItem]),
    OptionGroup("Checks", [RedRingChecks, RankChecks, GameLandChecks, ChaosEmeraldChecks, WispDiscoveryChecks]),
    OptionGroup("Game Land", [GameLandRequirementReduction, RedRingBundleStrategy]),
    OptionGroup("Experimental", [LevelRandomization, MusicRandomization, DeathLink]),
    OptionGroup("Traps", [TrapPercentage, RingLossTrapWeight, SwimTrapWeight, SwimTrapDuration]),
]
