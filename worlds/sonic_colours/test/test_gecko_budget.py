import re
from ..client.capsule_refresh import gecko_ini, HOOK as CAPSULE
from ..client.gameplay_controls import HOOKS
from ..client.medal_hook import HOOK as MEDAL
from ..client.progression_hook import HOOK as PROGRESSION


def pairs():
    return [tuple(int(word,16) for word in line.split())
            for line in gecko_ini().splitlines()
            if re.fullmatch('[0-9A-F]{8} [0-9A-F]{8}',line)]


def test_four_groups_fit_standard_dolphin_handler_and_reach_medal():
    # Standard codehandler.bin = 2880 bytes. GCT magic occupies its final
    # eight bytes; installation starts at 80001800 and ends at 80003000.
    capacity=0x3000-(0x1800+2880)-8
    assert len(pairs())*8 <= capacity
    assert any(first==0xC2000000|(MEDAL-0x80000000) for first,_ in pairs())


def test_shared_guard_installs_all_real_controls_once_and_rejects_wrong_disc():
    table=pairs()
    def run(memory):
        enabled=True; installed=[];i=0
        while i<len(table):
            first,second=table[i];i+=1
            kind=first>>24;address=0x80000000+(first&0xffffff)
            if kind in (0x20,0x28):
                enabled=enabled and memory.get(address)==second
            elif kind==0xc2:
                if enabled:
                    memory[address]=0x48000000
                    installed.append(address)
                i+=second  # payload words are not interpreted as Gecko codes
            elif kind==0xe0:
                enabled=True
            elif kind==0x04:
                if enabled:memory[address]=second
            else:raise AssertionError(hex(first))
        return installed
    memory={0x80000000:0x534e4350,0x80000004:0x3850,0x80000006:0}
    for first,second in table:
        if first>>24==0x20:memory[0x80000000+(first&0xffffff)]=second
    from ..client.map_refresh import HOOK as MAP
    from ..client.map_transition import HOOK as TRANSITION, UPDATE_HOOK
    from ..client.player_switch import HOOK as ASSIST
    from ..client.stunts import HOOK as STUNTS
    expected={CAPSULE,PROGRESSION,MEDAL,MAP,TRANSITION,UPDATE_HOOK}|{a for name,(a,_) in HOOKS.items() if name!='boost'}
    from ..client.drill_turbo import HOOK as DRILL
    from ..client.hover_ring_dash import HOOK as HOVER
    expected|={ASSIST,STUNTS,DRILL,HOVER}
    from ..client.map_ring_display import HOOK as RINGS
    expected.add(RINGS)
    wrong={**memory,0x80000000:0}
    assert run(wrong)==[]
    assert set(run(memory))==expected
    assert run(memory)==[]
    assert HOOKS['boost'][0] not in expected


def test_combined_export_contains_each_progressive_wisp_gate():
    from ..client.movement_gecko import movement_ini,pairs as movement_pairs,CAPACITY_BYTES
    from ..client.drill_turbo import HOOK as DRILL
    from ..client.hover_ring_dash import HOOK as HOVER
    table=movement_pairs(movement_ini())
    assert len(table)*8<=CAPACITY_BYTES
    for hook in (DRILL,HOVER):
        assert sum(first==0xC2000000|(hook-0x80000000) for first,_ in table)==1
