import json
from pathlib import Path

from BaseClasses import ItemClassification, Tutorial
from worlds.AutoWorld import WebWorld, World

from . import Items, Locations, Regions, Rules
from .data import GAME, HOLES, WORLDS
from .Options import MiniGolfOptions, OPTION_GROUPS


class MiniGolfWeb(WebWorld):
    theme = "partyTime"
    option_groups = OPTION_GROUPS
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
    item_name_groups = {"World Access": set(Items.UNLOCKS), "Coin Bundles": set(Items.COIN_BUNDLES),
                        "Par Club Pieces": set(Items.PAR_CLUB_PIECES),
                        "Coin Traps": set(Items.COIN_TRAPS), "Traps": set(Items.COIN_TRAPS)}
    location_name_groups = {name: {n for n, d in Locations.LOCATION_TABLE.items() if d.world == i}
                            for i, name in enumerate(WORLDS)}

    item_name_groups['Currency'] = set(Items.COIN_BUNDLES) | {Items.BARKER_COIN}
    location_name_groups.update({label: {n for n, d in Locations.LOCATION_TABLE.items() if d.kind in kinds}
                                for label, kinds in {
                                    'Hole Completions': {'complete'}, 'Par Club Pieces': {'par'},
                                    'Hole-in-Ones': {'hio'}, 'Minigames': {'win', 'perfect'},
                                    'World Secrets': {'secret'}, 'Pro Shop': {'shop', 'club'},
                                    'Barker Shop': {'barker_shop'}}.items()})

    def generate_early(self):
        passthrough = getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game)
        if passthrough:
            self.starting_world = passthrough["starting_world"]
            self.goal_mode = passthrough["goal"]
            self.goal_world = passthrough["goal_world"]
            self.barker_access = self.goal_mode == 1 and passthrough["goal_world_access"] == 1
            self.counter_mode = passthrough["counter_mode"]
            self.required_coins = passthrough["required_coins"]
            self.total_barker_coins = passthrough["total_barker_coins"]
            self.active_locations = tuple(passthrough["locations"])
            for name, value in passthrough.get("options", {}).items():
                if hasattr(self.options, name):
                    getattr(self.options, name).value = value
            self.options.starting_world.value = self.starting_world
            self.options.goal.value = self.goal_mode
            if self.goal_world is not None:
                self.options.goal_world.value = self.goal_world
            self.options.goal_world_access.value = passthrough["goal_world_access"]
            self.options.barker_coins_required.value = self.required_coins or passthrough.get(
                "options", {}).get("barker_coins_required", self.options.barker_coins_required.value)
            self.early_world_accesses = passthrough.get("early_world_accesses", [])
            if not self.early_world_accesses and passthrough.get("early_world_access") is not None:
                self.early_world_accesses = [passthrough["early_world_access"]]
            return

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
        capacity = (len(self.active_locations) - unlock_count
                    - (27 if self.options.shop_checks else 0)
                    - (1 if self.goal_world is not None else 0))
        if self.counter_mode:
            # Keep enough non-Barker slots for every World Access item. The
            # required coins always remain in the pool; only optional surplus
            # coins are trimmed when the smallest location set is selected.
            safe_coin_capacity = max(self.required_coins, capacity - unlock_count)
            self.total_barker_coins = min(self.total_barker_coins, safe_coin_capacity)
        if self.required_coins + unlock_count > available or self.required_coins > capacity:
            raise ValueError("Carnival Games MiniGolf: Too few enabled checks before the goal for the required "
                             "Barker Coins and world unlocks. Enable Barker Coin Checks, Secrets, Shops or "
                             f"Minigames, or reduce Barker Coins Required to {min(available - unlock_count, capacity)}.")
        self.early_world_accesses = []
        if self.counter_mode:
            candidates = [i for i in range(len(WORLDS)) if i not in (self.starting_world, self.goal_world)]
            self.random.shuffle(candidates)
            self.early_world_accesses = candidates

    def create_regions(self):
        Regions.create_regions(self)

    def set_rules(self):
        Rules.set_rules(self)

    def create_items(self):
        chained_accesses = set(self.early_world_accesses)
        names = [name for i, name in enumerate(Items.UNLOCKS)
                 if i not in (self.starting_world, self.goal_world) and i not in chained_accesses]
        if self.options.shop_checks:
            for name in Items.PAR_CLUB_PIECES:
                names.extend([name] * 3)
        # Barker counter modes reserve their small-pool capacity for the required
        # Barker Coins. Other goals always receive the bounded high-value bundles.
        if not self.counter_mode:
            for world in range(len(WORLDS)):
                names.extend([Items.coin_bundle_name(world, 500)] * Items.PROGRESSION_BUNDLES_PER_WORLD)
            for amount, count in Items.USEFUL_BUNDLE_COUNTS.items():
                names.extend(Items.coin_bundle_name(world, amount)
                             for world in self.random.sample(range(len(WORLDS)), count))
        names.extend([Items.BARKER_COIN] * self.total_barker_coins)
        locked_locations = 0
        chain_world = self.starting_world
        for access_world in self.early_world_accesses:
            self.get_location(f"{HOLES[chain_world * 3]} - Complete").place_locked_item(
                self.create_item(Items.UNLOCKS[access_world]))
            locked_locations += 1
            chain_world = access_world
        if self.goal_world is not None:
            if self.barker_access:
                self.get_location(Locations.BARKER_REQUIREMENT_LOCATION).place_locked_item(
                    self.create_item(Items.UNLOCKS[self.goal_world]))
                locked_locations += 1
            else:
                names.append(Items.UNLOCKS[self.goal_world])
        while len(names) < len(self.active_locations) - locked_locations:
            names.append(self.get_filler_item_name())
        barker_count = 0
        for name in names:
            item = self.create_item(name)
            if name == Items.BARKER_COIN and self.counter_mode:
                barker_count += 1
                if barker_count > self.required_coins:
                    item.classification = ItemClassification.useful
            self.multiworld.itempool.append(item)

    def create_item(self, name):
        classification = ItemClassification.trap if name in Items.COIN_TRAPS else ItemClassification.filler
        bundle = Items.COIN_BUNDLE_DATA.get(name)
        if bundle and bundle[1] in (100, 200):
            classification = ItemClassification.useful
        if ((bundle and bundle[1] == 500)
                or name in Items.UNLOCKS
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
        amount = self.random.choices(tuple(Items.FILLER_COIN_BUNDLE_WEIGHTS),
                                     weights=tuple(Items.FILLER_COIN_BUNDLE_WEIGHTS.values()), k=1)[0]
        return Items.coin_bundle_name(self.random.randrange(9), amount)

    def fill_slot_data(self):
        return {"schema_version": 9, "game": GAME, "seed_name": self.multiworld.seed_name,
                "starting_world": self.starting_world, "goal_world": self.goal_world,
                "goal": self.goal_mode, "goal_world_access": self.options.goal_world_access.value,
                "counter_mode": self.counter_mode, "required_coins": self.required_coins,
                "total_barker_coins": self.total_barker_coins,
                "early_world_accesses": self.early_world_accesses,
                "locations": {name: {'code': Locations.LOCATION_TABLE[name].code} for name in self.active_locations},
                "options": self.options.as_dict("starting_world", "goal_world", "goal", "minigame_checks",
                                                "hole_in_one_checks", "barker_coin_checks", "world_secrets",
                                                "shop_checks", "barker_shop_checks", "goal_world_access",
                                                "barker_coins_required", "trap_weight")}

    @staticmethod
    def interpret_slot_data(slot_data):
        return slot_data

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
