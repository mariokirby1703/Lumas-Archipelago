import json
from dataclasses import asdict
from pathlib import Path

from BaseClasses import ItemClassification, Tutorial
from worlds.AutoWorld import WebWorld, World

from . import Items, Locations, Regions, Rules
from .data import GAME, WORLDS
from .Options import MiniGolfOptions


class MiniGolfWeb(WebWorld):
    theme = "partyTime"
    tutorials = [Tutorial("Multiworld Setup", "Connect Carnival Games MiniGolf to Archipelago using Dolphin.",
                          "English", "setup_en.md", "setup/en", ["Luma"])]


class CarnivalGamesMiniGolfWorld(World):
    """Explore nine carnival worlds, earn Par Club Pieces, and discover prizes in Wii minigolf."""
    game = GAME
    web = MiniGolfWeb()
    options_dataclass = MiniGolfOptions
    options: MiniGolfOptions
    required_client_version = (0, 6, 7)
    counter_mode = False  # Item-link proxy worlds do not run generate_early.
    item_name_to_id = Items.ITEM_TABLE
    location_name_to_id = {name: data.code for name, data in Locations.LOCATION_TABLE.items()}
    item_name_groups = {"World Unlocks": set(Items.UNLOCKS), "Coin Bundles": set(Items.COIN_BUNDLES),
                        "Par Club Pieces": set(Items.PAR_CLUB_PIECES),
                        "Coin Traps": set(Items.COIN_TRAPS), "Traps": set(Items.COIN_TRAPS)}
    location_name_groups = {name: {n for n, d in Locations.LOCATION_TABLE.items() if d.world == i}
                            for i, name in enumerate(WORLDS)}

    def generate_early(self):
        self.starting_world = self.options.starting_world.value
        self.goal_mode = self.options.goal.value
        self.goal_world = self.options.goal_world.value if self.goal_mode == 1 else None
        if self.goal_world is not None:
            if self.goal_world == self.starting_world:
                # Standard AP `random` is resolved before world generation and can
                # independently roll the same value for both choices.
                self.goal_world = self.random.choice([i for i in range(9) if i != self.starting_world])
        self.barker_access = self.goal_mode == 1 and self.options.goal_world_access.value == 1
        self.counter_mode = self.goal_mode == 2 or self.barker_access
        self.required_coins = self.options.barker_coins_required.value if self.counter_mode else 0
        self.total_barker_coins = (self.required_coins * 3 + 1) // 2
        if self.counter_mode:
            self.options.barker_shop_checks.value = 0
        active = [n for n, d in Locations.LOCATION_TABLE.items() if Locations.enabled(d, self.options)]
        if self.barker_access:
            active.append(Locations.BARKER_REQUIREMENT_LOCATION)
        self.active_locations = tuple(active)
        unlock_count = 7 if self.goal_world is not None else 8
        available = sum(Locations.LOCATION_TABLE[n].world != self.goal_world
                        for n in self.active_locations if n != Locations.BARKER_REQUIREMENT_LOCATION)
        if self.total_barker_coins + unlock_count > available:
            raise ValueError("Carnival Games MiniGolf: Too few enabled checks before the goal for the required "
                             "Barker Coins and world unlocks. Enable Barker Coin Checks, Secrets, Shops or "
                             f"Minigames, or reduce Barker Coins Required to {available - unlock_count}.")

    def create_regions(self):
        Regions.create_regions(self)

    def set_rules(self):
        Rules.set_rules(self)

    def create_items(self):
        names = [name for i, name in enumerate(Items.UNLOCKS) if i not in (self.starting_world, self.goal_world)]
        if self.options.shop_checks:
            for name in Items.PAR_CLUB_PIECES:
                names.extend([name] * 3)
        names.extend([Items.BARKER_COIN] * self.total_barker_coins)
        locked_locations = 0
        if self.goal_world is not None:
            if self.barker_access:
                self.get_location(Locations.BARKER_REQUIREMENT_LOCATION).place_locked_item(
                    self.create_item(Items.GOAL_WORLD_ACCESS))
                locked_locations = 1
            else:
                names.append(Items.GOAL_WORLD_ACCESS)
        while len(names) < len(self.active_locations) - locked_locations:
            names.append(self.get_filler_item_name())
        self.multiworld.itempool.extend(self.create_item(name) for name in names)

    def create_item(self, name):
        classification = ItemClassification.trap if name in Items.COIN_TRAPS else ItemClassification.filler
        if (name in Items.UNLOCKS or name == Items.GOAL_WORLD_ACCESS
                or (name in Items.PAR_CLUB_PIECES and bool(getattr(self.options, 'shop_checks', True)))
                or (name == Items.BARKER_COIN and self.counter_mode)):
            classification = ItemClassification.progression
        return Items.MiniGolfItem(name, classification, Items.ITEM_TABLE[name], self.player)

    def get_filler_item_name(self):
        if self.random.randrange(100) < self.options.trap_weight.value:
            amount = self.random.choices(tuple(Items.COIN_TRAP_WEIGHTS),
                                         weights=tuple(Items.COIN_TRAP_WEIGHTS.values()), k=1)[0]
            return Items.coin_trap_name(self.random.randrange(9), amount)
        if not self.counter_mode and self.random.randrange(10) == 0:
            return Items.BARKER_COIN
        amount = self.random.choices(tuple(Items.COIN_BUNDLE_WEIGHTS),
                                     weights=tuple(Items.COIN_BUNDLE_WEIGHTS.values()), k=1)[0]
        return Items.coin_bundle_name(self.random.randrange(9), amount)

    def fill_slot_data(self):
        return {"schema_version": 5, "game": GAME, "seed_name": self.multiworld.seed_name,
                "starting_world": self.starting_world, "goal_world": self.goal_world,
                "goal": self.goal_mode, "goal_world_access": self.options.goal_world_access.value,
                "counter_mode": self.counter_mode, "required_coins": self.required_coins,
                "total_barker_coins": self.total_barker_coins,
                "locations": {name: asdict(Locations.LOCATION_TABLE[name]) for name in self.active_locations},
                "options": self.options.as_dict("goal", "minigame_checks", "hole_in_one_checks", "barker_coin_checks",
                                                "world_secrets", "shop_checks", "barker_shop_checks",
                                                "goal_world_access", "trap_weight")}

    def generate_output(self, output_directory):
        data = {"game": GAME, "player_name": self.multiworld.get_player_name(self.player),
                "slot_data": self.fill_slot_data()}
        path = Path(output_directory) / f"{self.multiworld.get_out_file_name_base(self.player)}.apcgm"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def write_spoiler_header(self, spoiler_handle):
        spoiler_handle.write(f"\nStarting World: {WORLDS[self.starting_world]}\n")
        if self.goal_world is not None:
            spoiler_handle.write(f"Goal World: {WORLDS[self.goal_world]}\n")
            access = "Barker Coins" if self.barker_access else "World Unlock Item"
            spoiler_handle.write(f"Goal World Access: {access}\n")
