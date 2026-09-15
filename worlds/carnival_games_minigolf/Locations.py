from dataclasses import dataclass

from BaseClasses import Location

from .data import BASE_ID, GAME, HOLES, MINIGAMES, PRIZES, WORLDS


@dataclass(frozen=True)
class LocationData:
    code: int
    kind: str
    index: int
    world: int | None
    pieces: int = 0


class MiniGolfLocation(Location):
    game = GAME


LOCATION_TABLE = {}
for i, hole in enumerate(HOLES):
    LOCATION_TABLE[f"{hole} - Complete"] = LocationData(BASE_ID + 300 + i, "complete", i, i // 3)
for kind, label, offset in (("par", "Par Club Piece", 0), ("barker", "Barker Coin", 30),
                             ("hio", "Hole-in-One", 60)):
    for i, hole in enumerate(HOLES):
        LOCATION_TABLE[f"{hole} - {label}"] = LocationData(BASE_ID + offset + i, kind, i, i // 3)
for prize in PRIZES:
    region = WORLDS[prize['world']] if prize['world'] is not None else "Barker Shop"
    if prize['kind'] in ("shop", "barker_shop"):
        location_name = f"{region} Shop: {prize['name']}" if prize['kind'] == "shop" else f"{region}: {prize['name']}"
    else:
        label = {"club": "Par Club Reward", "secret": "Secret"}[prize['kind']]
        location_name = f"{region} - {label}: {prize['name']}"
    LOCATION_TABLE[location_name] = LocationData(
        BASE_ID + 100 + prize['id'], prize['kind'], prize['id'], prize['world'], prize['pieces'])
for i, (name, _) in enumerate(MINIGAMES):
    for j, kind in enumerate(("win", "perfect")):
        LOCATION_TABLE[f"{name} - {kind.title()}"] = LocationData(BASE_ID + 200 + 2*i + j, kind, i, i)

BARKER_REQUIREMENT_LOCATION = "Barker Coin Goal Requirement"
LOCATION_TABLE[BARKER_REQUIREMENT_LOCATION] = LocationData(BASE_ID + 400, "barker_requirement", 0, None)


def enabled(data, options):
    return {
        "complete": True, "par": True, "barker": bool(options.barker_coin_checks), "hio": bool(options.hole_in_one_checks),
        "secret": bool(options.world_secrets), "shop": bool(options.shop_checks), "club": bool(options.shop_checks),
        "barker_shop": bool(options.barker_shop_checks),
        "win": bool(options.minigame_checks.value & 1), "perfect": bool(options.minigame_checks.value & 2),
        "barker_requirement": False,
    }[data.kind]
