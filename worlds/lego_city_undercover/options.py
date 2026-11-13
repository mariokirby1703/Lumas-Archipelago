from dataclasses import dataclass
from Options import Choice, Toggle, DefaultOnToggle, Range, PerGameCommonOptions


class StoryMode(Choice):
    """Requested native story layout. Experimental client does not yet enforce this setting."""
    display_name='Story Mode (native setup not implemented)'
    option_linear=0
    option_open_world=1
    default=0


class ShieldChecks(Choice):
    """Choose whole shields or four quarters. Native pickup detection remains experimental."""
    display_name='Police Shield Checks'
    option_off=0
    option_whole=1
    option_quarters=2
    default=2


class GoalTokens(Range):
    """Number of City Completion Tokens to receive to finish the experimental seed."""
    range_start=1
    range_end=500
    default=20


class UnsafeCandidates(Toggle):
    """Include raw clues and unbound pickup records. Many are prerequisites or duplicate rewards, not independent checks."""
    display_name='Include Unverified Candidates'


@dataclass
class LCUOptions(PerGameCommonOptions):
    story_mode: StoryMode
    super_bricks: DefaultOnToggle
    super_builds: DefaultOnToggle
    disguise_booths: DefaultOnToggle
    atms: DefaultOnToggle
    train_stations: DefaultOnToggle
    city_activities: DefaultOnToggle
    story_missions: DefaultOnToggle
    red_bricks: DefaultOnToggle
    city_hero: DefaultOnToggle
    police_shields: ShieldChecks
    include_unverified: UnsafeCandidates
    goal_tokens: GoalTokens
    character_items: DefaultOnToggle
    vehicle_items: DefaultOnToggle
    ability_items: DefaultOnToggle
    area_pass_items: Toggle
    story_access_items: Toggle
    cutscene_skip: DefaultOnToggle


def enabled_categories(options):
    categories={name for name in ('super_bricks','super_builds','disguise_booths','atms',
                'train_stations','city_activities','story_missions','red_bricks','city_hero')
                if getattr(options,name).value}
    if options.police_shields.value==1:categories.add('whole_shields')
    if options.police_shields.value==2:categories.add('shield_quarters')
    if options.include_unverified.value:categories.update(('unverified_clues','unverified_pickups'))
    return categories
