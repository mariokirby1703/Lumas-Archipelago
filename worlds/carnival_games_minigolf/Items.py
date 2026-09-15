from BaseClasses import Item

from .data import BASE_ID, GAME, WORLDS

BARKER_COIN = "Barker Coin"
GOAL_WORLD_ACCESS = "Goal World Access"
PAR_CLUB_PIECES = tuple(f"{world} Par Club Piece" for world in WORLDS)
UNLOCKS = tuple(f"Unlock {world}" for world in WORLDS)
# Relative frequencies within the bundle pool, as agreed with the user.
COIN_BUNDLE_WEIGHTS = {5: 1, 10: 2, 20: 8, 50: 16, 100: 16, 200: 6, 500: 4}
COIN_TRAP_WEIGHTS = {5: 4, 10: 3, 20: 2, 50: 1}


def coin_bundle_name(world, amount):
    return f"{WORLDS[world]} - Coin Bundle ({amount} Coins)"


COIN_BUNDLE_DATA = {coin_bundle_name(world, amount): (world, amount)
                    for world in range(9) for amount in COIN_BUNDLE_WEIGHTS}
COIN_BUNDLES = tuple(COIN_BUNDLE_DATA)


def coin_trap_name(world, amount):
    return f"{WORLDS[world]} - Coin Trap (-{amount} Coins)"


COIN_TRAP_DATA = {coin_trap_name(world, amount): (world, amount)
                  for world in range(9) for amount in COIN_TRAP_WEIGHTS}
COIN_TRAPS = tuple(COIN_TRAP_DATA)
ITEM_TABLE = {name: BASE_ID + i for i, name in enumerate(UNLOCKS)}
ITEM_TABLE[BARKER_COIN] = BASE_ID + 20
ITEM_TABLE[GOAL_WORLD_ACCESS] = BASE_ID + 21
ITEM_TABLE.update({name: BASE_ID + 300 + i for i, name in enumerate(PAR_CLUB_PIECES)})
# Reserve the provisional 30..38 IDs; never reinterpret an old bundle as a different amount.
ITEM_TABLE.update({name: BASE_ID + 100 + i for i, name in enumerate(COIN_BUNDLES)})
ITEM_TABLE.update({name: BASE_ID + 200 + i for i, name in enumerate(COIN_TRAPS)})


class MiniGolfItem(Item):
    game = GAME
