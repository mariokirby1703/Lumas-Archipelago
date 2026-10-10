from BaseClasses import Item, ItemClassification
from .world_constants import BASE_ID, GAME, WORLDS, WISPS

WORLD_ITEMS = tuple(f'{w} Access' for w in WORLDS)
WISP_ITEMS = tuple(f'{w} Wisp' for w in WISPS)
EMERALDS = tuple(f'{colour} Chaos Emerald' for colour in
                 ('Green', 'Red', 'Blue', 'Yellow', 'Purple', 'Cyan', 'White'))
RING_VALUES = {'Red Ring': 1, '5 Red Rings': 5, '10 Red Rings': 10}
LEGACY_FILLER = ('Rings (+10)', 'Rings (+25)', 'Rings (+50)')
FILLER = ('Rings', '1-Up', 'Half Boost Refill')
TRAPS = ('Ring Loss Trap', 'Swim Everywhere Trap')
NAMES = WORLD_ITEMS + WISP_ITEMS + EMERALDS + tuple(RING_VALUES) + LEGACY_FILLER + ('1-Up',) + TRAPS
# Offset 22 is retired. Existing counter/filler/trap IDs must not move.
ITEM_TABLE = {name: BASE_ID + i + (1 if i >= 22 else 0) for i, name in enumerate(NAMES)}
ITEM_TABLE.update({'Rings': BASE_ID + 32, 'Half Boost Refill': BASE_ID + 33})
GAME_LAND_SPEED = 'Progressive Game Land Speed'
ITEM_TABLE[GAME_LAND_SPEED] = BASE_ID + 34
BY_ID = {value: name for name, value in ITEM_TABLE.items()}


class SonicColoursItem(Item):
    game = GAME


def classification(name):
    if name == GAME_LAND_SPEED:
        return ItemClassification.useful
    if name in TRAPS:
        return ItemClassification.trap
    if name in FILLER + LEGACY_FILLER:
        return ItemClassification.filler
    return ItemClassification.progression


def ring_name(value):
    return next(name for name, amount in RING_VALUES.items() if amount == value)
