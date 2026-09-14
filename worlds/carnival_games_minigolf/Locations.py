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
for kind, label, offset in (("par", "Par Club Piece", 0), ("barker", "Barker Coin", 30),
                             ("hio", "Hole-in-One", 60)):
    for i, hole in enumerate(HOLES):
        LOCATION_TABLE[f"{hole} - {label}"] = LocationData(BASE_ID + offset + i, kind, i, i // 3)
for prize in PRIZES:
    region = WORLDS[prize['world']] if prize['world'] is not None else "Barker Shop"
    label = {"shop": "Purchase", "barker_shop": "Purchase", "club": "Par Club Reward", "secret": "Secret"}[prize['kind']]
    LOCATION_TABLE[f"{region} - {label}: {prize['name']}"] = LocationData(
        BASE_ID + 100 + prize['id'], prize['kind'], prize['id'], prize['world'], prize['pieces'])
for i, (name, _) in enumerate(MINIGAMES):
    for j, kind in enumerate(("win", "perfect")):
        LOCATION_TABLE[f"{name} - {kind.title()}"] = LocationData(BASE_ID + 200 + 2*i + j, kind, i, i)


def enabled(data, options):
    return {
        "par": True, "barker": bool(options.barker_coin_checks), "hio": bool(options.hole_in_one_checks),
        "secret": bool(options.world_secrets), "shop": bool(options.shop_checks), "club": bool(options.shop_checks),
        "barker_shop": bool(options.barker_shop_checks),
        "win": bool(options.minigame_checks.value & 1), "perfect": bool(options.minigame_checks.value & 2),
    }[data.kind]
