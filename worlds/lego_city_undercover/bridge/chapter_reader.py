"""Typed read-only original chapter-event bank; never AP completion or activation.

The original Start action records a per-player event flag, not an active chapter
selector. Save isolation of the achievements bank is not established.
"""
import struct
from inventory_reader import pointer
MANAGER_RVA=0x17EBD00
VTABLE_RVA=0xC10988

def parse_chapter_mask(value):
    if type(value) is not int or not 0<=value<2**32:raise ValueError('Invalid chapter mask')
    return [number for number in range(1,16) if value&(1<<number)]

def read_chapter_events(read,base):
    profile=pointer(read,base+0x1C7F160);manager=pointer(read,base+MANAGER_RVA)
    if not manager or not profile:return dict(status='not_initialized',check_eligible=False)
    if pointer(read,manager)!=base+VTABLE_RVA:raise ValueError('Unsupported LegoAchievements layout')
    first=read(manager+0x110,4);second=read(manager+0x188,4)
    if (pointer(read,base+MANAGER_RVA)!=manager or pointer(read,base+0x1C7F160)!=profile or
            read(manager+0x110,4)!=first or read(manager+0x188,4)!=second):
        raise RuntimeError('Chapter event bank changed during read')
    masks=[struct.unpack('<I',value)[0] for value in (first,second)]
    return dict(status='native_chapter_event_bank',manager=hex(manager),profile=hex(profile),
        reported_completed=[parse_chapter_mask(value) for value in masks],raw_masks=[hex(value) for value in masks],
        active_chapter=None,check_eligible=False,activation_supported=False,native_save_isolation_verified=False,
        evidence='SAction_MarkChapterComplete 0x84b0 -> 0x7cf0; first player +0x110, stride 0x78; not a chapter selector')
