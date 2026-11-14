from dataclasses import dataclass
from Options import Choice, Toggle, DefaultOnToggle, Range, PerGameCommonOptions


class StoryMode(Choice):
    """Linear guarantees Police on a known opening check and gates remaining experimental checks behind it.
    Open world keeps the experimental unrestricted catalogue. Other ability logic and native open-world setup are incomplete."""
    display_name='Story Mode (partial opening logic)'
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


class SuperBricks(DefaultOnToggle):
    """Select city Super Brick source checks. Some source bindings remain experimental."""
    display_name='Super Bricks'


class SuperBuilds(DefaultOnToggle):
    """Select Super Build objective checks; native rewards are not suppressed."""
    display_name='Super Builds'


class DisguiseBooths(DefaultOnToggle):
    """Select disguise booth activation checks."""
    display_name='Disguise Booths'


class ATMs(DefaultOnToggle):
    """Select ATM destruction objective checks, not ordinary ATM use."""
    display_name='Atms'


class TrainStations(DefaultOnToggle):
    """Select train station activation objectives."""
    display_name='Train Stations'


class CityActivities(DefaultOnToggle):
    """Select other native city activity objectives."""
    display_name='City Activities'


class StoryMissions(DefaultOnToggle):
    """Include story mission completions and the three opening clown-robber arrests."""
    display_name='Story Missions'


class RedBricks(DefaultOnToggle):
    """Include experimental red brick source checks; immediate pickup detection remains incomplete."""
    display_name='Red Bricks'


class CityHero(DefaultOnToggle):
    """Include experimental LEGO City Hero checks without native binding."""
    display_name='City Hero'


class CharacterItems(DefaultOnToggle):
    """Add character receipt items. The opt-in native client grants ownership without purchase."""
    display_name='Character Items'


class VehicleItems(DefaultOnToggle):
    """Add vehicle receipt items. Native model grants are experimental."""
    display_name='Vehicle Items'


class AbilityItems(DefaultOnToggle):
    """Add ability receipt items. Bound native tools can be granted and vanilla tool rewards suppressed; symbolic abilities remain unbound."""
    display_name='Ability Items'


class AreaPassItems(Toggle):
    """Add experimental area-pass items. Native district gating is unavailable."""
    display_name='Area Pass Items'


class StoryAccessItems(Toggle):
    """Add experimental story-access items. Native entrance gating is unavailable."""
    display_name='Story Access Items'


class CutsceneSkip(DefaultOnToggle):
    """Request native cutscene skip permission. Client writes require explicit opt-in."""
    display_name='Cutscene Skip'


class CharacterTokens(DefaultOnToggle):
    """Character token source checks, including story missions. Found-flag bindings are experimental; duplicate sources remain unbound."""
    display_name='Character Token Checks'


class VehicleTokens(DefaultOnToggle):
    """Vehicle token source checks. Discovery counts; purchasing or equipping does not create a check."""
    display_name='Vehicle Token Checks'


class CheatItems(DefaultOnToggle):
    """Include Red Brick cheat items. Native effect bindings are experimental."""
    display_name='Red Brick Cheat Items'


class SuperBrick1000Count(Range):
    """Number of useful 1,000 building-brick packages requested in the pool."""
    display_name='1,000 Super Brick Packages'
    range_start=0
    range_end=500
    default=20


class SuperBrick10000Count(Range):
    """Number of useful 10,000 building-brick packages requested in the pool."""
    display_name='10,000 Super Brick Packages'
    range_start=0
    range_end=100
    default=5


@dataclass
class LCUOptions(PerGameCommonOptions):
    cheat_items: CheatItems
    super_brick_1000_count: SuperBrick1000Count
    super_brick_10000_count: SuperBrick10000Count
    character_tokens: CharacterTokens
    vehicle_tokens: VehicleTokens
    story_mode: StoryMode
    super_bricks: SuperBricks
    super_builds: SuperBuilds
    disguise_booths: DisguiseBooths
    atms: ATMs
    train_stations: TrainStations
    city_activities: CityActivities
    story_missions: StoryMissions
    red_bricks: RedBricks
    city_hero: CityHero
    police_shields: ShieldChecks
    include_unverified: UnsafeCandidates
    goal_tokens: GoalTokens
    character_items: CharacterItems
    vehicle_items: VehicleItems
    ability_items: AbilityItems
    area_pass_items: AreaPassItems
    story_access_items: StoryAccessItems
    cutscene_skip: CutsceneSkip


def enabled_categories(options):
    categories={name for name in ('super_bricks','super_builds','disguise_booths','atms',
                'train_stations','city_activities','story_missions','red_bricks','city_hero','character_tokens','vehicle_tokens')
                if getattr(options,name).value}
    if options.police_shields.value==1:categories.add('whole_shields')
    if options.police_shields.value==2:categories.add('shield_quarters')
    if options.include_unverified.value:categories.update(('unverified_clues','unverified_pickups'))
    return categories
