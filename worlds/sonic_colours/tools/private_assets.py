from pathlib import Path
import os


def reference_root(world_root=None):
    if world_root is None and os.environ.get('SONIC_COLOURS_REFERENCE_DIR'):
        return Path(os.environ['SONIC_COLOURS_REFERENCE_DIR']).resolve()
    world_root=Path(world_root) if world_root is not None else Path(__file__).resolve().parents[1]
    return world_root.resolve().parents[1]/'build'/'sonic_colours_reference'
