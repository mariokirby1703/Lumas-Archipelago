from BaseClasses import Item, ItemClassification
from .world_constants import BASE_ID, GAME, WORLDS, WISPS, wisp_item

WORLD_ITEMS = tuple(f'{w} Shuttle' for w in WORLDS[:6])
WISP_ITEMS = tuple(wisp_item(w) for w in WISPS)
EMERALDS = tuple(f'{colour} Chaos Emerald' for colour in
                 ('Green', 'Red', 'Blue', 'Yellow', 'Purple', 'Cyan', 'White'))
RING_VALUES = {'Red Ring': 1, '5 Red Rings': 5, '10 Red Rings': 10}
LEGACY_FILLER = ('Rings (+10)', 'Rings (+25)', 'Rings (+50)')
FILLER_WEIGHTS = {'Rings': 40, '1-Up': 30, 'Half Boost Refill': 20, 'Full Boost Refill': 10}
FILLER = tuple(FILLER_WEIGHTS)
TRAPS = ('Ring Loss Trap', 'Score Reset Trap', 'Dead Weight Trap')
# Keep retired Terminal Velocity Access offset 6 out of the public item table.
NAMES = tuple(f'{w} Shuttle' for w in WORLDS) + WISP_ITEMS + EMERALDS + tuple(RING_VALUES) + LEGACY_FILLER + ('1-Up',) + ('Ring Loss Trap','Swim Everywhere Trap')
# Offset 22 is retired. Existing counter/filler/trap IDs must not move.
ITEM_TABLE = {name: BASE_ID + i + (1 if i >= 22 else 0) for i, name in enumerate(NAMES)}
ITEM_TABLE.pop('Terminal Velocity Shuttle')
ITEM_TABLE.update({'Rings': BASE_ID + 32, 'Half Boost Refill': BASE_ID + 33})
GAME_LAND_SPEED = 'Progressive Game Land Speed'
ITEM_TABLE[GAME_LAND_SPEED] = BASE_ID + 34
RANDOM_CAPSULES = 'Random Capsules'
ITEM_TABLE[RANDOM_CAPSULES] = BASE_ID + 35
ITEM_TABLE['Full Boost Refill'] = BASE_ID + 36
# Append-only IDs. Never renumber existing Archipelago inventory/locations.
MOVEMENT_ITEMS = ('Wall Jump', 'Homing Attack', 'Mid-Air Boost', 'Double Jump',
                  'Stomp', 'Progressive Crouch', 'Swim', 'Breath')
MOVEMENT_POOL = ('Wall Jump', 'Homing Attack', 'Mid-Air Boost', 'Double Jump',
                 'Stomp', 'Progressive Crouch', 'Progressive Crouch', 'Swim', 'Breath')
ITEM_TABLE.update({name: BASE_ID + 37 + i for i, name in enumerate(MOVEMENT_ITEMS)})
ITEM_TABLE['Progressive Breathing'] = BASE_ID + 45
MOVEMENT_ITEMS = MOVEMENT_ITEMS[:-1] + ('Progressive Breathing',)
MOVEMENT_POOL = MOVEMENT_POOL[:-1] + ('Progressive Breathing',)*5
ITEM_TABLE['Drifting'] = BASE_ID + 46
MOVEMENT_ITEMS += ('Drifting',)
MOVEMENT_POOL += ('Drifting',)
ITEM_TABLE['Assist Change'] = BASE_ID + 47
MOVEMENT_ITEMS += ('Assist Change',)
MOVEMENT_POOL += ('Assist Change',)
ITEM_TABLE['Progressive Stunts'] = BASE_ID + 48
MOVEMENT_ITEMS += ('Progressive Stunts',)
MOVEMENT_POOL += ('Progressive Stunts',)*5
ITEM_TABLE['Progressive Rail'] = BASE_ID + 49
MOVEMENT_ITEMS += ('Progressive Rail',)
MOVEMENT_POOL += ('Progressive Rail',)*2
# Offset 50 is retired; decode old Rail Switch receipts without generating them.
ITEM_TABLE['Progressive Skydiving'] = BASE_ID + 51
MOVEMENT_ITEMS += ('Progressive Skydiving',)
MOVEMENT_POOL += ('Progressive Skydiving',)*2
ITEM_TABLE['Quick Step'] = BASE_ID + 52
ITEM_TABLE.pop('Swim Everywhere Trap')
ITEM_TABLE['Score Reset Trap'] = BASE_ID + 53
ITEM_TABLE['Dead Weight Trap'] = BASE_ID + 54
NORMAL_WISP_ITEMS = ('Yellow Drill Wisp','Green Hover Wisp','Pink Spikes Wisp')
ITEM_TABLE.update({name:BASE_ID+55+i for i,name in enumerate(NORMAL_WISP_ITEMS)})
RING_VALUES.update({'20 Red Rings':20,'50 Red Rings':50})
ITEM_TABLE.update({'20 Red Rings':BASE_ID+58,'50 Red Rings':BASE_ID+59})
ALL_WISP_ITEMS = WISP_ITEMS + NORMAL_WISP_ITEMS
MOVEMENT_ITEMS += ('Quick Step',)
MOVEMENT_POOL += ('Quick Step',)
BY_ID = {value: name for name, value in ITEM_TABLE.items()}
BY_ID[BASE_ID + 50] = 'Rail Switch'
BY_ID[BASE_ID + 31] = 'Swim Everywhere Trap'  # decode retired receipts only


class SonicColoursItem(Item):
    game = GAME


def classification(name):
    if name == RANDOM_CAPSULES:
        return ItemClassification.useful  # Capsule Sanity promotes it per world.
    if name == GAME_LAND_SPEED:
        return ItemClassification.progression
    if name in TRAPS:
        return ItemClassification.trap
    if name in FILLER + LEGACY_FILLER:
        return ItemClassification.filler
    return ItemClassification.progression


def ring_name(value):
    return next(name for name, amount in RING_VALUES.items() if amount == value)
