"""Import the actual ZIP through AP's package scheme and fill a seed from it."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import unittest
import zipimport
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
os.environ['AP_TEST_WORLDS']='generic'
import worlds
from worlds.Files import APWorldContainer
from BaseClasses import MultiWorld,CollectionState
from Fill import distribute_items_restrictive


def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);args=parser.parse_args()
    archive=args.archive.resolve();container=APWorldContainer(str(archive));container.read()
    name='worlds.'+archive.stem;loader=zipimport.zipimporter(str(archive));spec=loader.find_spec(name)
    if spec is None:raise RuntimeError('Archive filename and package root do not match')
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    world_type=module.LCUWorld
    multi=MultiWorld(1);multi.game[1]=world_type.game;multi.player_name={1:'ArchiveTest'};multi.set_seed(2048)
    options=argparse.Namespace()
    for key,option in world_type.options_dataclass.type_hints.items():setattr(options,key,{1:option.from_any(option.default)})
    multi.set_options(options);multi.state=CollectionState(multi);world=multi.worlds[1]
    world.generate_early();world.create_regions();world.create_items();world.pre_fill();distribute_items_restrictive(multi)
    assert multi.can_beat_game()
    assert str(archive) in module.__file__
    print(f'OK: {archive.name}: ZIP import, manifest {container.world_version}, {len(multi.regions)} regions, beatable restrictive fill')


if __name__=='__main__':main()
