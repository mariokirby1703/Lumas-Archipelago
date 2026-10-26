from pathlib import Path


def reference_root(world_root=None):
    world_root=Path(world_root) if world_root is not None else Path(__file__).resolve().parents[1]
    return world_root.resolve().parents[1]/'build'/'sonic_colours_reference'
