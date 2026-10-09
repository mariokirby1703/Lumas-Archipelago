from BaseClasses import Item, ItemClassification
from .world_constants import BASE_ID, GAME, WORLDS, WISPS

WORLD_ITEMS = tuple(f'{w} Access' for w in WORLDS)
WISP_ITEMS = tuple(f'{w} Wisp' for w in WISPS)
EMERALDS = tuple(f'{colour} Chaos Emerald' for colour in
                 ('Green', 'Red', 'Blue', 'Yellow', 'Purple', 'Cyan', 'White'))
RING_VALUES = {'Red Ring (+1)': 1, 'Red Rings (+5)': 5, 'Red Rings (+10)': 10}
FILLER = ('Rings (+10)', 'Rings (+25)', 'Rings (+50)', '1-Up')
TRAPS = ('Ring Loss Trap', 'Swim Everywhere Trap')
NAMES = WORLD_ITEMS + WISP_ITEMS + EMERALDS + tuple(RING_VALUES) + FILLER + TRAPS
# Offset 22 is retired. Existing counter/filler/trap IDs must not move.
ITEM_TABLE = {name: BASE_ID + i + (1 if i >= 22 else 0) for i, name in enumerate(NAMES)}
BY_ID = {value: name for name, value in ITEM_TABLE.items()}


class SonicColoursItem(Item):
    game = GAME


def classification(name):
    if name in TRAPS:
        return ItemClassification.trap
    if name in FILLER:
        return ItemClassification.filler
    return ItemClassification.progression


def ring_name(value):
    return next(name for name, amount in RING_VALUES.items() if amount == value)
