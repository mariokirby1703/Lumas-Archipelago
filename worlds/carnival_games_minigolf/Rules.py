from worlds.generic.Rules import set_rule

from .Items import BARKER_COIN, UNLOCKS
from .Locations import LOCATION_TABLE
from .data import HOLES, PRIZES, WORLDS


def world_access(world, index):
    if index == world.starting_world:
        return lambda state: True
    if index == world.goal_world:
        return lambda state: state.has(BARKER_COIN, world.player, world.required_coins)
    return lambda state: state.has(UNLOCKS[index], world.player)


def par_count(state, world, index):
    # Par pieces are local accomplishments, not randomized inventory items.
    # Reachable par checks mean that the player can earn these pieces.
    return sum(state.can_reach(f"{HOLES[i]} - Par Club Piece", "Location", world.player)
               for i in range(index * 3, index * 3 + 3))


def set_rules(world):
    for i, name in enumerate(WORLDS):
        set_rule(world.get_entrance(f"Menu -> {name}"), world_access(world, i))
    shop_cost = 0
    barker_costs = {}
    for prize in sorted((p for p in PRIZES if p['kind'] == 'barker_shop'), key=lambda p: (p['price'], p['id'])):
        shop_cost += prize['price']
        barker_costs[prize['id']] = shop_cost
    for name in world.active_locations:
        data = LOCATION_TABLE[name]
        if data.pieces:
            set_rule(world.get_location(name), lambda state, d=data: par_count(state, world, d.world) >= d.pieces)
        elif data.kind == 'barker_shop':
            # All 27 vanilla Barker collectibles remain obtainable even when their checks are disabled.
            set_rule(world.get_location(name), lambda state, cost=barker_costs[data.index]:
                     sum(3 for i in range(9) if world_access(world, i)(state)) >= cost)
    def victory(state):
        if world.goal_world is not None:
            return (state.has(BARKER_COIN, world.player, world.required_coins)
                    and par_count(state, world, world.goal_world) == 3)
        if world.counter_mode:
            return state.has(BARKER_COIN, world.player, world.required_coins)
        return all(par_count(state, world, i) == 3 for i in range(9))
    world.multiworld.completion_condition[world.player] = victory
