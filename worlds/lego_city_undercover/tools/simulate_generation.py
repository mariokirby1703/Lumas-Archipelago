"""Real restrictive fills, spheres and beatability; no native/game writes."""
import argparse
import json
import logging
import sys
import time
from argparse import Namespace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from BaseClasses import MultiWorld,CollectionState
from worlds.lego_city_undercover import LCUWorld
from Fill import distribute_items_restrictive

PROFILES=(
    ('chronological',dict(early_criminal_scan=True,early_detective_scan=True)),
    ('whole_shields',dict(police_shields='whole')),
    ('no_shields',dict(police_shields='off')),
    ('all_assignments',dict(goal='all_assignments')),
    ('legacy_debug_goal',dict(goal='debug_tokens')),
    ('unrestricted_story_order',dict(story_mode='open_world')),
    ('starting_police',dict(start_inventory={'Ability: Police':1})),
    ('starting_astronaut',dict(start_inventory={'Ability: Astronaut':1})),
    ('legacy_astronaut',dict(progressive_astronaut=False)),
    ('no_cosmetics',dict(character_items=False,separate_class_unlocks=False)),
    ('no_vehicles',dict(vehicle_items=False)),
    ('multiworld',dict(early_criminal_scan=True,early_detective_scan=True)),
    ('area_rollback_test',dict(area_pass_items=True,experimental_area_restrictions=True,early_criminal_scan=True,early_detective_scan=True)),
    ('area_multiworld',dict(area_pass_items=True,experimental_area_restrictions=True)),
    ('legacy_police',dict(progressive_police=False)),
    ('legacy_robber_firefighter',dict(progressive_robber=False,progressive_firefighter=False)),
    ('starting_progressive_police',dict(start_inventory={'Progressive Police':1})),
    ('starting_grapple',dict(start_inventory={'Ability: GrappleGun':1})),
)


def simulate(seed,changes,players):
    multi=MultiWorld(players);multi.player_name={p:f'LCU{p}' for p in multi.player_ids};multi.set_seed(seed)
    for p in multi.player_ids:multi.game[p]=LCUWorld.game
    args=Namespace()
    for name,option in LCUWorld.options_dataclass.type_hints.items():
        setattr(args,name,{p:option.from_any(changes.get(name,option.default)) for p in multi.player_ids})
    multi.set_options(args);multi.state=CollectionState(multi)
    for world in multi.worlds.values():world.generate_early()
    # Match Main.py's start_inventory handling before pool construction.
    for p in multi.player_ids:
        for name,count in multi.worlds[p].options.start_inventory.value.items():
            for _ in range(count):multi.push_precollected(multi.worlds[p].create_item(name))
    for stage in ('create_regions','create_items','pre_fill'):
        for world in multi.worlds.values():getattr(world,stage)()
    distribute_items_restrictive(multi)
    if not multi.can_beat_game():raise AssertionError('Seed is not beatable')
    spheres=[dict(index=i,locations=len(sphere),progression=sum(bool(l.item and l.item.advancement) for l in sphere))
             for i,sphere in enumerate(multi.get_spheres())]
    reachable=sum(s['locations'] for s in spheres)
    if reachable!=len(multi.get_locations()):raise AssertionError('Unreachable locations')
    return dict(seed=seed,players=players,beatable=True,locations=reachable,spheres=spheres,
                native_playability_proven=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--count',type=int,default=120)
    parser.add_argument('--output',type=Path,default=ROOT/'build/lego_city_undercover/master_task/generation_simulations.json')
    args=parser.parse_args();logging.getLogger().setLevel(logging.ERROR);rows=[];start=time.monotonic()
    for i in range(args.count):
        name,changes=PROFILES[i%len(PROFILES)]
        try:row=simulate(10000+i,changes,2 if name in ('multiworld','area_multiworld') else 1)
        except Exception as error:row=dict(seed=10000+i,error=str(error),beatable=False)
        row['profile']=name;rows.append(row)
    report=dict(count=len(rows),passed=sum(r['beatable'] for r in rows),elapsed_seconds=time.monotonic()-start,
                limitation='AP logical fill simulation, not an in-game completion proof',results=rows)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f"{report['passed']}/{len(rows)} seeds passed; {args.output}")
    if report['passed']!=len(rows):raise SystemExit(1)


if __name__=='__main__':main()
