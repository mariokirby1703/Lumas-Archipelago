from dataclasses import dataclass
from Options import Choice, DefaultOnToggle, Toggle, Range, DeathLink, PerGameCommonOptions, OptionGroup, Visibility

class Goal(Choice):
    """Choose what you must complete to finish your run. Final Boss includes the escape in Terminal Velocity Act 2."""
    display_name = 'Goal'
    option_nega_wisp_armor = 0
    option_all_bosses = 1
    option_all_red_rings = 2
    default = 0

    @classmethod
    def get_option_name(cls, value):
        return 'Nega-Wisp Armor (Final Boss)' if value == 0 else super().get_option_name(value)


class RedRingChecks(Choice):
    """Add a check for each physical Red Ring, or one check per Act for collecting all five.
    These pickups are separate from the AP Red Ring items used to open Game Land stages."""
    display_name = 'Red Ring Checks'
    option_off = 0
    option_singles = 1
    option_per_level = 2
    default = 1


class RankChecks(Choice):
    """Choose the lowest rank that gives a check.
    Better ranks also complete lower enabled ranks.
    All adds S, A, B and C checks."""
    display_name = 'Rank Checks'
    option_off = 0
    option_s = 1
    option_a = 2
    option_b = 3
    option_c = 4
    option_all = 6
    default = 0


class RingLossTrapWeight(Choice):
    """How often Ring Loss Traps appear compared with other traps."""
    display_name = 'Ring Loss Trap Weight'
    option_off = 0
    option_low = 1
    option_medium = 2
    option_high = 3
    default = 2


class ScoreResetTrapWeight(Choice):
    """How often Score Reset Traps appear compared with other traps."""
    display_name = 'Score Reset Trap Weight'
    option_off = 0
    option_low = 1
    option_medium = 2
    option_high = 3
    default = 1


class MusicRandomization(DefaultOnToggle):
    """Shuffle music across everywhere."""
    display_name = 'Music Randomization'


class DeadWeightTrapWeight(Choice):
    """Relative frequency of Dead Weight Traps. Blocks jumping for 30 seconds of gameplay."""
    display_name = 'Dead Weight Trap Weight'
    option_off = 0
    option_low = 1
    option_medium = 2
    option_high = 3
    default = 1


class WorldProgression(Choice):
    """Unlock Acts in Order: each clear opens the next Act like in Vanilla.
    All Acts then Boss: unlocking a world opens all six Acts independently; clear all six to open its boss."""
    display_name = 'World Progression'
    option_unlock_acts_in_order = 0
    option_all_acts_then_boss = 1
    alias_sequential = 0
    alias_open_acts = 1
    default = 0


class GameLandChecks(DefaultOnToggle):
    """Add a Clear check for each of the 21 Game Land stages.
    Stages require AP Red Ring items to unlock. When off, also disables
    Eggman Heart Sanity and Chaos Emerald Checks and removes Red Ring items."""
    display_name = 'Game Land Checks'


class SuperSonic(Toggle):
    """Add the seven Chaos Emerald items to the pool to unlock Super Sonic.
    When Off, Chaos Emerald items are not added to the pool."""
    display_name = 'Super Sonic'


class ChaosEmeraldChecks(Toggle):
    """Add a check for clearing all three stages in each Game Land group, for seven checks total.
    This does not grant the matching AP Chaos Emerald item."""
    display_name = 'Chaos Emerald Checks'


class WispDiscoveryChecks(DefaultOnToggle):
    """Add a check when you first discover each coloured Wisp.
    Discovery does not unlock its AP ability."""
    display_name = 'Wisp Discovery Checks'


class GameLandRequirementReduction(Range):
    """Percentage-based reduction for Game Land Stage unlock costs."""
    display_name = 'Game Land Requirement Reduction'
    range_start = 0
    range_end = 99
    default = 50


class TrapPercentage(Range):
    """Percentage of remaining filler slots replaced with traps."""
    display_name = 'Trap Percentage'
    range_start = 0
    range_end = 100
    default = 10


class WispCapsules(Toggle):
    """Add checks for collectible Wisp Capsules.
    Available through YAML while hidden from the standard options UI."""
    display_name = 'Wisp Capsule Sanity'
    visibility = Visibility.none


class OneUpSanity(Toggle):
    """Add checks for the 31 1-Up objects spread across the 36 Acts."""
    display_name = '1-Up Sanity'


class EggmanHeartSanity(DefaultOnToggle):
    """Add a check for collecting the Eggman Heart in each Game Land stage."""
    display_name = 'Eggman Heart Sanity'


class SonicDeathLink(DeathLink):
    """Share deaths with other players."""
    display_name = 'Death Link'


class MovementUnlocks(DefaultOnToggle):
    """Lock all kinds of movement abilities.
    Includes abilities like double jump, wall jump etc."""
    display_name = 'Ability Locks'


class BoostLock(DefaultOnToggle):
    """Require White Boost Wisp to gain Boost from white capsules and enemies.
    AP Boost Refills remain usable."""
    display_name = 'White Boost Wisp Lock'


class NativeFeatureTests(Toggle):
    """Developer opt-in for other unfinished PAL native experiments.
    DeathLink and Dead Weight can be selected normally, but are not live-verified."""
    display_name = 'Unverified Native Feature Tests'
    visibility = Visibility.none


@dataclass
class SonicColoursOptions(PerGameCommonOptions):
    goal: Goal
    world_progression: WorldProgression
    boost_lock: BoostLock
    movement_unlocks: MovementUnlocks
    super_sonic: SuperSonic
    red_ring_checks: RedRingChecks
    rank_checks: RankChecks
    one_up_sanity: OneUpSanity
    wisp_discovery_checks: WispDiscoveryChecks
    game_land_checks: GameLandChecks
    chaos_emerald_checks: ChaosEmeraldChecks
    eggman_heart_sanity: EggmanHeartSanity
    game_land_requirement_reduction: GameLandRequirementReduction
    trap_percentage: TrapPercentage
    ring_loss_trap_weight: RingLossTrapWeight
    score_reset_trap_weight: ScoreResetTrapWeight
    dead_weight_trap_weight: DeadWeightTrapWeight
    music_randomization: MusicRandomization
    death_link: SonicDeathLink
    wisp_capsules: WispCapsules
    native_feature_tests: NativeFeatureTests

OPTION_NAMES = tuple(SonicColoursOptions.__annotations__)

OPTION_GROUPS = [
    OptionGroup('Progression', [Goal, WorldProgression, BoostLock, MovementUnlocks, SuperSonic]),
    OptionGroup('Checks', [RedRingChecks, RankChecks, OneUpSanity, WispDiscoveryChecks]),
    OptionGroup('Game Land', [GameLandChecks, ChaosEmeraldChecks, EggmanHeartSanity, GameLandRequirementReduction]),
    OptionGroup('Traps', [TrapPercentage, RingLossTrapWeight, ScoreResetTrapWeight, DeadWeightTrapWeight]),
    OptionGroup('Miscellaneous', [MusicRandomization, SonicDeathLink]),
]
