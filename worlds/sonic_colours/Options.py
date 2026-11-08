from dataclasses import dataclass
from Options import OptionSet, Choice, DefaultOnToggle, Toggle, Range, DeathLink, PerGameCommonOptions, OptionGroup, Visibility

class Goal(Choice):
    """Choose what you must complete to finish your run. Nega Wisp Armor includes the escape in Terminal Velocity Act 2."""
    display_name = 'Goal'
    option_nega_wisp_armor = 0
    option_all_bosses = 1
    option_all_red_rings = 2
    default = 0

    @classmethod
    def get_option_name(cls, value):
        return 'Nega-Wisp Armor (Final Boss)' if value == 0 else super().get_option_name(value)


class RedRingChecks(Choice):
    """Red Ring checks are always enabled: one per ring, or one per Act for collecting all five.
    These pickups are separate from the AP Red Ring items used to open Game Land stages."""
    display_name = 'Red Ring Checks'
    option_singles = 1
    option_per_level = 2
    default = 1

    @classmethod
    def from_any(cls, data):
        if data == 0 or isinstance(data,str) and data.lower() in ('off','false','0'):
            return cls(cls.option_singles)
        return super().from_any(data)


class RankChecks(OptionSet):
    """Select any ranks that should have checks: C, B, A and S. Example: [B, S]
    A better result also completes selected lower-rank checks.
    Leave the selection empty to disable rank checks."""
    display_name = 'Rank Checks'
    valid_keys = {'C', 'B', 'A', 'S'}
    default = frozenset()

    @classmethod
    def from_any(cls, data):
        if isinstance(data, dict):
            from Generate import get_choice
            return cls.from_any(get_choice('rank_checks', {'rank_checks':data}, 'off'))
        if type(data) is int:
            legacy = {0:(), 1:('S',), 2:('A',), 3:('B',), 4:('C',), 6:('C','B','A','S')}
            if data not in legacy:raise ValueError('Invalid legacy Rank Checks value')
            return cls(legacy[data])
        if data is None or data is False:return cls(())
        if isinstance(data,str):return cls.from_text(data)
        if not isinstance(data,(list,tuple,set,frozenset)):
            raise ValueError('Rank Checks must be a selection of C, B, A and S')
        if any(not isinstance(rank,str) for rank in data):raise ValueError('Invalid rank name')
        option=cls([rank.strip().upper() for rank in data])
        option.verify_keys()
        return option

    @classmethod
    def from_text(cls, text):
        text=text.strip()
        if text.lower() in ('off','false','none',''):return cls(())
        if text.lower()=='all':return cls(cls.valid_keys)
        if text.isdigit():return cls.from_any(int(text))
        if text.lower().startswith('random'):return super().from_text(text)
        return cls.from_any([rank.strip() for rank in text.split(',')])


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


class SixtyFPS(Toggle):
    """Run the game at 60 FPS.

    Known physics issues affect loops, springs and the final boss. 
    Leave off if you are unsure, but it would only require you to restart the act if you encounter issues."""
    display_name = "60 FPS"


class MusicRandomization(DefaultOnToggle):
    """Shuffle music across everywhere."""
    display_name = 'Music Randomization'


class DeadWeightTrapWeight(Choice):
    """Relative frequency of Dead Weight Traps. Low makes them very rare compared with other enabled traps. Blocks jumping for 10 seconds; the timer continues during pauses and on maps."""
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
    default = 1


class GameLandChecks(DefaultOnToggle):
    """Add a Clear check for each of the 21 Game Land stages.
    Stages require AP Red Ring items to unlock. When off, also disables
    Eggman Heart Sanity and Chaos Emerald Checks and removes Red Ring items."""
    display_name = 'Game Land Checks'


class SuperSonic(Toggle):
    """Add the seven Chaos Emerald items to the pool to unlock Super Sonic.
    The logic for this feature is not fully implemented, so you may be able to collect red rings out of logic."""
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
    """Developer opt-in for other unfinished native experiments."""
    display_name = 'Unverified Native Feature Tests'
    visibility = Visibility.none


class RedRingItemColors(DefaultOnToggle):
    """Color Red Rings by their AP rewards: purple for progression, blue for useful and light blue for filler."""
    display_name = 'Red Ring Item Colors'


class ColorblindMode(Toggle):
    """Use gold, blue, gray and orange for progression, useful, filler and traps in Red Ring colors and the item HUD.
    Own rewards and disguised traps still follow their separate settings below."""
    display_name = 'Colorblind Mode'


class Luma(Choice):
    """Use Luma's Red Ring palette."""
    display_name = 'Luma'
    visibility = Visibility.none
    option_off = 0
    option_luma = 1
    default = 0


class OwnItemRedRingColors(Choice):
    """Keep your own rewards red, keep only your own AP Red Ring currency red, or color every reward by item type. Traps use their separate setting below."""
    display_name = 'Own Item Red Ring Colors'
    option_always_red = 0
    option_red_ring_items_only = 1
    option_item_classification = 2
    default = 2


class TrapRedRingColors(Choice):
    """Keep traps red (orange in Colorblind Mode), or disguise them with a fixed random item color."""
    display_name = 'Trap Red Ring Colors'
    option_red = 0
    option_random_colors = 1
    default = 1

    @classmethod
    def from_text(cls, text):
        if text.lower() == 'random':
            return cls(cls.option_random_colors)
        return super().from_text(text)


TrapRedRingColors.options['random'] = TrapRedRingColors.option_random_colors
TrapRedRingColors.name_lookup = {0: 'red', 1: 'random'}


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
    sixty_fps: SixtyFPS
    death_link: SonicDeathLink
    wisp_capsules: WispCapsules
    native_feature_tests: NativeFeatureTests
    red_ring_item_colors: RedRingItemColors
    colorblind_mode: ColorblindMode
    luma: Luma
    own_item_red_ring_colors: OwnItemRedRingColors
    trap_red_ring_colors: TrapRedRingColors

OPTION_NAMES = tuple(SonicColoursOptions.__annotations__)

OPTION_GROUPS = [
    OptionGroup('Progression', [Goal, WorldProgression, BoostLock, MovementUnlocks, SuperSonic]),
    OptionGroup('Checks', [RedRingChecks, RankChecks, OneUpSanity, WispDiscoveryChecks]),
    OptionGroup('Game Land', [GameLandChecks, ChaosEmeraldChecks, EggmanHeartSanity, GameLandRequirementReduction]),
    OptionGroup('Traps', [TrapPercentage, RingLossTrapWeight, ScoreResetTrapWeight, DeadWeightTrapWeight]),
    OptionGroup('Red Ring Colors', [RedRingItemColors, ColorblindMode, OwnItemRedRingColors, TrapRedRingColors]),
    OptionGroup('Miscellaneous', [MusicRandomization, SixtyFPS, SonicDeathLink]),
]
