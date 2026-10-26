import re


def _records(lines):
    rows=[tuple(int(word,16) for word in line.split()) for line in lines
          if re.fullmatch(r'[0-9A-F]{8} [0-9A-F]{8}',line)]
    result=[];i=0
    while i<len(rows):
        first,second=rows[i];i+=1
        kind=first>>24
        if kind==0xc2:
            if second<1 or i+second>len(rows):
                raise ValueError('Truncated native hook payload')
            result.append((first,second));result.extend(rows[i:i+second]);i+=second
        elif kind==4:
            result.append((first,second))
        elif kind not in (0x20,0x28,0xe0):
            raise ValueError(f'Unknown native patch record {first:#x}')
    return result


def hook_rows():
    from . import (capsule_refresh,progression_hook,gameplay_controls,medal_hook,
                   map_transition,map_ring_display,game_land_menu,game_land_native_tint,
                   player_switch,speed_initial,stunts,drill_turbo,hover_ring_dash,
                   oneup_hook,movement_gate,skydiving,quick_step)
    words=capsule_refresh.payload_words(compact_abi=True,epilogue_abi=True,cache_permissions=True)
    rows=[(0xc2000000|(capsule_refresh.HOOK-0x80000000),len(words)//2)]
    rows.extend(zip(words[::2],words[1::2]))
    for module in (progression_hook,gameplay_controls,medal_hook,map_transition,
                   map_ring_display,game_land_menu,game_land_native_tint,player_switch,
                   speed_initial,stunts,drill_turbo,hover_ring_dash,oneup_hook,
                   movement_gate,skydiving,quick_step):
        rows.extend(_records(module.gecko_lines()))
    return rows
