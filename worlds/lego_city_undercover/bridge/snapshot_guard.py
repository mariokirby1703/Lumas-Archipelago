"""Reject mixed native snapshots, including fields read late in the collection."""
from inventory_reader import pointer
from delivery_marker import read_marker

def snapshot_identity(read,base):
    return (pointer(read,base+0x1C7F160),pointer(read,base+0x1C7D3E0),
            pointer(read,base+0x1C6A768),read_marker(read,base))

def verify_snapshot_identity(expected,read,base):
    if snapshot_identity(read,base)!=expected:
        raise RuntimeError('Native profile, actor, world or AP save binding changed during snapshot')
