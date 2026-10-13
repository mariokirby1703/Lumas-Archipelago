from dataclasses import dataclass
from Options import Choice, DefaultOnToggle, Toggle, Range, DeathLink, PerGameCommonOptions, OptionGroup

class Goal(Choice):
    """Nega-Wisp Armor (Final Boss) requires the final boss and the subsequent Terminal Velocity Act 2 escape. Other goals require all seven bosses, all 180 physical Red Rings, all 21 Game Land stages, or all seven AP Chaos Emeralds."""
    display_name = 'Goal'
    option_nega_wisp_armor = 0
    option_all_bosses = 1
    option_all_red_rings = 2
    option_all_game_land_stages = 3
    option_super_sonic = 4
    default = 0

    @classmethod
    def get_option_name(cls, value):
        return 'Nega-Wisp Armor (Final Boss)' if value == 0 else super().get_option_name(value)


class RedRingChecks(Choice):
    """Add a check for each physical Red Ring, or one check per Act for collecting all five. These pickups are separate from the AP Red Ring items used to open Game Land stages."""
    display_name = 'Red Ring Checks'
    option_off = 0
    option_singles = 1
    option_per_level = 2
    default = 1


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


class MusicRandomization(DefaultOnToggle):
    """Shuffle all 78 looping BGM cues in one global pool, including Acts, maps, bosses, menus, Game Land and Wisps. The nine finite tracks stay vanilla as sources and destinations. Destination audio controls are retained. Default On. Existing tracks may require a scene change."""
    display_name = 'Music Randomization'


class WorldProgression(Choice):
    """Sequential unlocks the next Act after clearing the previous one; Open Acts allows all six Acts and opens the boss only after all six are cleared."""
    display_name = 'World Progression'
    option_sequential = 0
    option_open_acts = 1
    default = 0


class GameLandChecks(DefaultOnToggle):
    """Add a Clear check for each of the 21 Game Land stages. All 21 stages require AP Red Ring items."""
    display_name = 'Game Land Checks'


class ChaosEmeraldChecks(DefaultOnToggle):
    """Adds seven location checks for obtaining the Chaos Emerald rewards in Game Land. Each reward is earned by completing all three stages in one of the seven Game Land worlds. The checks are separate from the seven Chaos Emerald progression items placed by Archipelago."""
    display_name = 'Chaos Emerald Checks'


class WispDiscoveryChecks(Toggle):
    """Add a check when the game first introduces each of the seven coloured Wisps through its vanilla discovery event. Opening ordinary capsules does not count, and discovery does not grant the corresponding AP Wisp item."""
    display_name = 'Wisp Discovery Checks'


class GameLandRequirementReduction(Range):
    """All 21 Game Land stages use one evenly spaced AP Red Ring requirement sequence: all Stage 1 gates, then Stage 2, then Stage 3. First gate requires 1. Step is max(1, floor((179 - reduction) / 20)). Reduction 113 gives 1, 4, 7 ... 61; default 40 gives 1, 7, 13 ... 121."""
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
    display_name = 'Wisp Capsule Sanity'


class EggmanHeartSanity(Toggle):
    """Add one immediate native Eggman Heart pickup check in each of the 21 Game Land stages. Requires the PAL Eggman Heart native pickup code; stage Ring gates and traversal requirements still apply."""
    display_name = 'Eggman Heart Sanity'


class SonicDeathLink(DeathLink):
    """Share deaths with other players. This client currently requires Off; native death delivery is not supported."""
    display_name = 'Death Link'


class MovementUnlocks(Toggle):
    """EXPERIMENTAL: shuffle Wall Jump, Homing Attack, Mid-Air Boost (Jump Dash),
    Double Jump, Stomp, Drifting, two Progressive Rail stages (Rail Jump then Rail Switch), two Progressive Skydiving stages (gliding then fast diving), Assist Change, five Progressive Stunts, 2 Progressive Crouch stages, Swim and five Progressive Breathing items.
    State-transition locks require the replacement Dolphin Movement Gecko BETA
    code profile and are NOT active with the ordinary four Gecko groups.
    Swim controls repeated underwater jumps independently of Double Jump.
    Air starts at zero; Progressive Breathing grants 5, 10, 20, 40, then 60 seconds.
    These gates require the current complete Movement profile.
    """
    display_name = 'Movement Unlocks (Experimental)'


class BoostLock(Toggle):
    """Require the White Boost Wisp item for ordinary Boost use. Off preserves vanilla Boost from the start. Super Sonic's native infinite Boost remains separate."""
    display_name = 'Boost Lock'


@dataclass
class SonicColoursOptions(PerGameCommonOptions):
    goal: Goal
    red_ring_checks: RedRingChecks
    world_progression: WorldProgression
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
    boost_lock: BoostLock
    movement_unlocks: MovementUnlocks
    wisp_capsules: WispCapsules
    eggman_heart_sanity: EggmanHeartSanity

OPTION_NAMES = tuple(SonicColoursOptions.__annotations__)

OPTION_GROUPS = [
    OptionGroup('Progression', [Goal, WorldProgression, BoostLock, MovementUnlocks]),
    OptionGroup('Checks', [RedRingChecks, RankChecks, GameLandChecks, ChaosEmeraldChecks, WispDiscoveryChecks, WispCapsules, EggmanHeartSanity]),
    OptionGroup('Game Land', [GameLandRequirementReduction]),
    OptionGroup('Presentation', [MusicRandomization]),
    OptionGroup('Gameplay', [SonicDeathLink]),
    OptionGroup('Traps', [TrapPercentage, RingLossTrapWeight, SwimTrapWeight, SwimTrapDuration]),
]
