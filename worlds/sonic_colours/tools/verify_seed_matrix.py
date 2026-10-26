"""Run from the repository root: python worlds/sonic_colours/tools/verify_seed_matrix.py.
AP_TEST_WORLDS=sonic_colours and SKIP_REQUIREMENTS_UPDATE=1 are recommended.
"""
import argparse
import itertools
import json
from pathlib import Path
import time
import unittest  # Keep test-world imports scoped by AP_TEST_WORLDS.
import os
import sys
import hashlib
os.environ.setdefault('AP_TEST_WORLDS','sonic_colours')
os.environ.setdefault('SKIP_REQUIREMENTS_UPDATE','1')
if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from worlds.sonic_colours.test import generate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',type=int,default=100)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.seeds<1:parser.error('--seeds must be positive')
    results=[];start=time.monotonic()
    root=Path(__file__).resolve().parents[1]
    source={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
            ('world.py','Rules.py','Items.py','Options.py','wisps.py','logic.py','data/logic_from_sheet_v3.json')}
    for boost,movement,land,capsules in itertools.product((0,1),repeat=4):
        options=dict(boost_lock=boost,movement_unlocks=movement,game_land_checks=land,wisp_capsules=capsules)
        for seed in range(args.seeds):
            multi=generate(options,seed,fill=True)
            if not multi.can_beat_game() or multi.get_unfilled_locations():raise AssertionError((options,seed))
        results.append(dict(options=options,seeds=args.seeds))
        print(options,args.seeds,'beatable complete fills',flush=True)
        if args.output:args.output.write_text(json.dumps({'source_sha256':source,'results':results,'seconds':time.monotonic()-start},indent=2))


if __name__=='__main__':main()
