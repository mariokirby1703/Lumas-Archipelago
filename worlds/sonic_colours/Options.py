from dataclasses import dataclass
from Options import Choice, DefaultOnToggle, Toggle, Range, DeathLink, PerGameCommonOptions, OptionGroup

class Goal(Choice):
    """Choose your victory condition: the final boss, all seven bosses, all 180 physical Red Rings, all 21 Game Land stages, or all seven AP Chaos Emeralds."""
    display_name = 'Goal'
    option_nega_wisp_armor = 0
    option_all_bosses = 1
    option_all_red_rings = 2
    option_all_game_land_stages = 3
    option_super_sonic = 4
    default = 0


class RedRingChecks(Choice):
    """Add a check for each physical Red Ring, or one check per Act for collecting all five. These pickups are separate from the AP Red Ring items used to open Game Land stages."""
    display_name = 'Red Ring Checks'
    option_off = 0
    option_singles = 1
    option_per_level = 2
    default = 1


class StartingAct(Choice):
    """Choose the first stage available after the original two-Act introduction. Random includes normal Acts, the six world bosses and Terminal Velocity Acts 1 and 2; it excludes the final boss."""
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
    option_tropical_resort_boss = 36
    option_sweet_mountain_boss = 37
    option_starlight_carnival_boss = 38
    option_planet_wisp_boss = 39
    option_aquarium_park_boss = 40
    option_asteroid_coaster_boss = 41
    option_terminal_velocity_act_1 = 42
    option_terminal_velocity_act_2 = 43
    default = 'random'


class LevelRandomization(Choice):
    """Shuffle normal Acts within each world or across worlds. This client currently requires Off; stage shuffling is not supported."""
    display_name = 'Level Randomization'
    option_off = 0
    option_per_world = 1
    option_anywhere = 2
    default = 0


class RankChecks(Choice):
    """Add minimum-grade checks for S, A, B or C. A better rank also completes every lower enabled threshold. All adds all four checks to each ranked stage."""
    display_name = 'Rank Checks'
    option_off = 0
    option_s = 1
    option_a = 2
    option_b = 3
    option_c = 4
    option_all = 6
    default = 0


class RingLossTrapWeight(Choice):
    """How often Ring Loss Traps appear among trap items. The trap removes Sonic's current rings when safely delivered during an Act."""
    display_name = 'Ring Loss Trap Weight'
    option_off = 0
    option_low = 1
    option_medium = 2
    option_high = 3
    default = 2


class SwimTrapWeight(Choice):
    """How often swimming traps appear. This client currently requires Off; swimming traps are not supported."""
    display_name = 'Swim Trap Weight'
    option_off = 0
    option_low = 1
    option_medium = 2
    option_high = 3
    default = 0


class MusicRandomization(Choice):
    """Shuffle music in normal Acts within each world or across worlds. The same seed uses the same shuffle. Changes apply after the original introduction; Off preserves vanilla music."""
    display_name = 'Music Randomization'
    option_off = 0
    option_per_world = 1
    option_anywhere = 2
    default = 0


class GameLandChecks(DefaultOnToggle):
    """Add a Clear check for each of the 21 Game Land stages. Every first stage is free; the second and third stages require AP Red Ring items."""
    display_name = 'Game Land Checks'


class ChaosEmeraldChecks(DefaultOnToggle):
    """Adds seven location checks for obtaining the Chaos Emerald rewards in Game Land. Each reward is earned by completing all three stages in one of the seven Game Land worlds. The checks are separate from the seven Chaos Emerald progression items placed by Archipelago."""
    display_name = 'Chaos Emerald Checks'


class WispDiscoveryChecks(Toggle):
    """Add a check when the game first introduces each of the seven coloured Wisps through its vanilla discovery event. Opening ordinary capsules does not count, and discovery does not grant the corresponding AP Wisp item."""
    display_name = 'Wisp Discovery Checks'


class GameLandRequirementReduction(Range):
    """Reduce the AP Red Ring counts needed for Game Land stages 2 and 3. Thresholds remain positive and strictly increasing. Stage 1 in every Game Land world always requires zero."""
    display_name = 'Game Land Requirement Reduction'
    range_start = 0
    range_end = 179
    default = 40


class TrapPercentage(Range):
    """Percentage of remaining filler slots replaced with traps. Progression items are never replaced."""
    display_name = 'Trap Percentage'
    range_start = 0
    range_end = 100
    default = 10


class SwimTrapDuration(Range):
    """Duration in seconds for swimming traps, when supported."""
    display_name = 'Swim Trap Duration'
    range_start = 5
    range_end = 60
    default = 15


class WispCapsules(Toggle):
    """Add an immediate check for every eligible collectible Wisp Capsule in story Acts and Game Land. Coloured capsules require their matching AP Wisp item."""
    display_name = 'Wisp Capsules'


class SonicDeathLink(DeathLink):
    """Share deaths with other players. This client currently requires Off; native death delivery is not supported."""
    display_name = 'Death Link'


@dataclass
class SonicColoursOptions(PerGameCommonOptions):
    goal: Goal
    wisp_capsules: WispCapsules
    red_ring_checks: RedRingChecks
    starting_act: StartingAct
    level_randomization: LevelRandomization
    rank_checks: RankChecks
    ring_loss_trap_weight: RingLossTrapWeight
    swim_trap_weight: SwimTrapWeight
    music_randomization: MusicRandomization
    game_land_checks: GameLandChecks
    chaos_emerald_checks: ChaosEmeraldChecks
    wisp_discovery_checks: WispDiscoveryChecks
    game_land_requirement_reduction: GameLandRequirementReduction
    trap_percentage: TrapPercentage
    swim_trap_duration: SwimTrapDuration
    death_link: SonicDeathLink

OPTION_NAMES = tuple(SonicColoursOptions.__annotations__)

OPTION_GROUPS = [
    OptionGroup('Progression', [Goal, StartingAct]),
    OptionGroup('Checks', [RedRingChecks, WispCapsules, RankChecks, GameLandChecks, ChaosEmeraldChecks, WispDiscoveryChecks]),
    OptionGroup('Game Land', [GameLandRequirementReduction]),
    OptionGroup('Presentation', [MusicRandomization]),
    OptionGroup('Gameplay', [LevelRandomization, SonicDeathLink]),
    OptionGroup('Traps', [TrapPercentage, RingLossTrapWeight, SwimTrapWeight, SwimTrapDuration]),
]
